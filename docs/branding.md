# Integration branding

Home Assistant 2026.3 and newer load custom-integration branding from
`custom_components/<domain>/brand/`. This integration ships the four standard
TCL assets at that location:

| File | Dimensions | Purpose |
| --- | ---: | --- |
| `icon.png` | 256 x 256 | Square integration icon |
| `icon@2x.png` | 512 x 512 | High-density integration icon |
| `logo.png` | 213 x 128 | Configuration-page logo |
| `logo@2x.png` | 425 x 256 | High-density configuration-page logo |

These files are direct copies of the identical TCL asset set already maintained
by Home Assistant Brands for both
[`tcl_home_unofficial`](https://github.com/home-assistant/brands/tree/master/custom_integrations/tcl_home_unofficial)
and
[`tcl_tv_remote`](https://github.com/home-assistant/brands/tree/master/custom_integrations/tcl_tv_remote).
Reusing the reviewed community assets keeps TCL integrations visually
consistent and avoids maintaining a separately redrawn logo.

The upstream set does not provide separate dark-mode images. Home Assistant
therefore uses the standard images as its documented fallback in dark mode.
The TCL name and logo remain the property of their respective owner and are
used only for product identification; their use does not imply endorsement or
affiliation.
