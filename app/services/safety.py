from urllib.parse import urlparse

DEFAULT_SAFE_DOMAINS = {
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "nih.gov", "who.int", "cdc.gov",
    "fda.gov", "ema.europa.eu", "nice.org.uk", "nhs.uk", "medlineplus.gov",
    "mayoclinic.org", "msdmanuals.com", "minzdrav.gov.ru", "cr.minzdrav.gov.ru",
    "cochranelibrary.com", "bmj.com", "nejm.org", "jamanetwork.com", "thelancet.com",
    # Patient-facing guidance from recognized medical societies and public health services.
    "radiologyinfo.org", "acr.org", "rsna.org", "cancer.gov", "healthdirect.gov.au",
    "labtestsonline.org.uk", "testing.com", "clevelandclinic.org",
    # Narrow, recognized weather providers used for explicitly weather-related
    # queries. Other queries still pass through topical relevance filtering.
    "gismeteo.ru", "meteoinfo.ru", "rp5.ru", "weather.com", "meteoblue.com",
    "open-meteo.com",
    # Local place discovery is used only when the query asks for nearby services
    # (for example cafes/restaurants); results still pass topic and evidence checks.
    "2gis.ru", "2gis.com", "yandex.ru", "yandex.com", "tripadvisor.ru",
    "tripadvisor.com", "restaurantguru.com", "restoclub.ru", "zoon.ru",
    "afisha.ru", "flamp.ru", "google.com",
}

LOCAL_DISCOVERY_SAFE_DOMAINS = {
    "2gis.ru", "2gis.com", "yandex.ru", "yandex.com", "tripadvisor.ru",
    "tripadvisor.com", "restaurantguru.com", "restoclub.ru", "zoon.ru",
    "afisha.ru", "flamp.ru", "google.com",
}

WEATHER_SAFE_DOMAINS = {
    "gismeteo.ru", "meteoinfo.ru", "rp5.ru", "weather.com", "meteoblue.com",
    "open-meteo.com",
}


def is_safe_domain(url: str, allowed_domains: set[str]) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not hostname:
        return False
    return any(hostname == domain or hostname.endswith("." + domain) for domain in allowed_domains)
