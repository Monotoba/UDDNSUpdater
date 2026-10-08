from .ddns_provider import DDNSProvider, ProviderError
import xml.etree.ElementTree as ET

class NamecheapDDNS(DDNSProvider):
    required_fields = ('domain', 'password', 'hostname')

    def update_ddns(self):
        external_ip = self.validate_ipv4(self.external_ip)
        text = self.request_text(
            "https://dynamicdns.park-your-domain.com/update",
            params={"host": self.config["hostname"], "domain": self.config["domain"],
                    "password": self.config["password"], "ip": external_ip},
        )
        if "<!DOCTYPE" in text.upper():
            raise ProviderError("Invalid Namecheap response.")
        try:
            root = ET.fromstring(text)
        except (ET.ParseError, ValueError):
            raise ProviderError("Invalid Namecheap response.") from None
        def single_value(tag):
            nodes = root.findall(tag)
            return nodes[0].text.strip() if len(nodes) == 1 and nodes[0].text else None
        if (root.tag != "interface-response" or single_value("ErrCount") != "0"
                or single_value("Done") != "true" or single_value("IP") != external_ip
                or any(len(node) or (node.text or "").strip()
                       for tag in ("errors", "Errors") for node in root.findall(tag))):
            raise ProviderError("Namecheap did not confirm the requested IPv4 update.")
        return True
