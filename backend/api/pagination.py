"""Shared deterministic page-number pagination with preserved filters."""

from django.core.paginator import EmptyPage, Paginator

from .errors import ApiProblem


def _positive(raw, name, default):
    if raw is None:
        return default
    if not raw.isdecimal() or int(raw) < 1:
        raise ApiProblem(
            "INVALID_FILTER",
            f"{name} must be a positive integer",
            details={name: "positive integer required"},
        )
    return int(raw)


def paginate(request, queryset, serialize):
    number = _positive(request.query_params.get("page"), "page", 1)
    size = _positive(request.query_params.get("page_size"), "page_size", 25)
    if size > 100:
        raise ApiProblem(
            "INVALID_FILTER",
            "page_size exceeds 100",
            details={"page_size": "maximum 100"},
        )
    paginator = Paginator(queryset, size)
    try:
        page = paginator.page(number)
    except EmptyPage:
        raise ApiProblem(
            "INVALID_FILTER",
            "Page is outside the result set",
            details={"page": "out of range"},
        ) from None

    def url(target):
        if target is None:
            return None
        query = request.query_params.copy()
        query["page"] = str(target)
        return request.build_absolute_uri(f"{request.path}?{query.urlencode()}")

    return {
        "count": paginator.count,
        "next": url(page.next_page_number() if page.has_next() else None),
        "previous": url(page.previous_page_number() if page.has_previous() else None),
        "results": [serialize(row) for row in page.object_list],
    }
