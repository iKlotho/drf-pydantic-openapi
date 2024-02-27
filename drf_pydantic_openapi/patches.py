# Override endpoint enumerator just like drf-spectacular to access path_regex
from django.urls import URLPattern, URLResolver
from rest_framework.schemas.generators import EndpointEnumerator


class CustomEndpointEnumerator(EndpointEnumerator):
    def endpoint_ordering(endpoint):
        path, path_regex, method, callback = endpoint
        method_priority = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}.get(method, 5)
        return (method_priority,)

    def get_api_endpoints(self, patterns=None, prefix=""):
        api_endpoints = self._get_api_endpoints(patterns, prefix)

        api_endpoints_deduplicated = {}
        for path, path_regex, method, callback in api_endpoints:
            if (path, method) not in api_endpoints_deduplicated:
                api_endpoints_deduplicated[path, method] = (path, path_regex, method, callback)

        api_endpoints = list(api_endpoints_deduplicated.values())

        return sorted(api_endpoints, key=self.endpoint_ordering)

    def get_path_from_regex(self, path_regex):
        path = super().get_path_from_regex(path_regex)
        # bugfix oversight in DRF regex stripping
        path = path.replace("\\.", ".")
        return path

    def _get_api_endpoints(self, patterns, prefix):
        """
        Return a list of all available API endpoints by inspecting the URL conf.
        Only modification the the DRF version is passing through the path_regex.
        """
        if patterns is None:
            patterns = self.patterns

        api_endpoints = []

        for pattern in patterns:
            path_regex = prefix + str(pattern.pattern)
            if isinstance(pattern, URLPattern):
                path = self.get_path_from_regex(path_regex)
                callback = pattern.callback
                if self.should_include_endpoint(path, callback):
                    for method in self.get_allowed_methods(callback):
                        endpoint = (path, path_regex, method, callback)
                        api_endpoints.append(endpoint)

            elif isinstance(pattern, URLResolver):
                nested_endpoints = self._get_api_endpoints(patterns=pattern.url_patterns, prefix=path_regex)
                api_endpoints.extend(nested_endpoints)

        return api_endpoints
