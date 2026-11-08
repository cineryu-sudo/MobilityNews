"""Official LG U+ BI logo embedded in outgoing mail."""

from pathlib import Path

LOGO_CID = "lguplus-logo"
# Official header logo from lguplus.com (static/pc-static/logo_uplus.png, 141x40).
LOGO_PATH = Path(__file__).parent / "assets" / "lguplus_logo.png"


def logo_img(width: int, height: int) -> str:
    """Return an <img> tag that references the inline logo attachment."""
    return (
        f'<img src="cid:{LOGO_CID}" width="{width}" height="{height}" alt="LG U+" '
        f'style="display:block;width:{width}px;height:{height}px;border:0;outline:none;'
        f'text-decoration:none;color:#303037;font-size:12px;font-weight:800;">'
    )
