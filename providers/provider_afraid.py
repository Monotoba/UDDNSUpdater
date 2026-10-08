"""Legacy Afraid class name for the FreeDNS.afraid.org direct-key adapter."""
from .provider_freedns import FreeDNS


class Afraid(FreeDNS):
    """Use api_key and hostname; account passwords are not update keys."""
