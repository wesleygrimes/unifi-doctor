"""UniFi API endpoint definitions."""


def stat_device(site: str) -> str:
    return f"/proxy/network/api/s/{site}/stat/device"


def stat_sta(site: str) -> str:
    return f"/proxy/network/api/s/{site}/stat/sta"


def stat_rogueap(site: str) -> str:
    return f"/proxy/network/api/s/{site}/stat/rogueap"


def rest_setting(site: str) -> str:
    return f"/proxy/network/api/s/{site}/rest/setting"


def stat_health(site: str) -> str:
    return f"/proxy/network/api/s/{site}/stat/health"


def stat_event(site: str) -> str:
    return f"/proxy/network/api/s/{site}/stat/event"


def rest_wlanconf(site: str) -> str:
    return f"/proxy/network/api/s/{site}/rest/wlanconf"


def stat_spectral(site: str) -> str:
    return f"/proxy/network/api/s/{site}/stat/spectralanalysis"


def stat_routing(site: str) -> str:
    return f"/proxy/network/api/s/{site}/stat/routing"


def device_mgmt(site: str, mac: str) -> str:
    """Endpoint to manage a specific device (for apply-plan)."""
    return f"/proxy/network/api/s/{site}/cmd/devmgr"


AUTH_LOGIN = "/api/auth/login"
