Generate OpenAPI schema with DRF code using pydantic models. Supports referencing other service's components.

# Usage

# Add urls to the project

```python
 urlpatters = [
    path("openapi/", include("drf_pydantic_openapi.urls")),
 ]
 ```

 - Available endpoints
    - `/schema.json` 
    - `/docs`

# Reference another openapi source

Add the following setting to your projects `settings.py`. This will allow the module to access to the other openapi components defined in seperate projects.
```python
# settings.py

DRF_PYDANTIC_OPENAPI = {
    "REF_SOURCES": {
        "service_B": "http://localhost:8000/openapi",
        "service_C": "http://localhost:8001/openapi",
    }
}
```

# Using a component defined in another service

```python
# views.py
from drf_pydantic_openapi.ref_utils import RefType

BookModel = RefType("service_B", "BookModel")

class BookView(ApiView):
    def get(self, request) -> BookModel:
        ...

# More complex example

class CustomBookModel(RefType("service_B", "BookModel")):
    # add new field
    read_count: int
    
    class Config:
        # Remove field from referenced type
        ref_exclude = ("author",)
        # Rename field
        ref_rename = (("book_name", "name"),)
        
class PaginatedBookModel(BaseModel):
    total: int
    next: str
    prev: str
    data: list[CustomBookModel]

class BookView(ApiView):
    def get(self, request) -> PaginatedBookModel:
        ...
```

# Using the `@docs`

- Parameters
    - body: Request body model
    - errors: List of error models
    - query: Query model
    - path: Api path parameter model
    
```python
from pydantic import BaseModel
from drf_pydantic_openapi.errors import BadRequestError, NotFoundError

class RetrieveQuery(BaseModel):
    book_id: str
    
class Path(BaseModel):
    book_id: str = Field(description="Book id to retrieve")


class BookView(ApiView):
    @docs(errors=[NotFoundError], query=RetrieveQuery, path=Path)
    def get(self, request):
        ...
...
```

# Typed exception handler

Assign the `typed_exception_handler` to rest framework. This will catch any ValidationError and the custom HttpError and return the response as json.
```python
# settings.py

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "drf_pydantic_openapi.exception_handler.typed_exception_handler"
}


```


```python
# Example
from drf_pydantic_openapi.errors import BadRequestError
class SomeView(ApiView):
    @docs(errors=[BadRequestError])
    def post(self, request):
        raise BadRequestError()

```

###  Response
```json
{
	"detail": {
		"message": "Bad request"
	}
}
```