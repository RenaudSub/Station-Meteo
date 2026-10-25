# Visual assets

The 15 animated weather WebP images, the transparent 3D compass and the two SVG arrows were supplied by the user for inclusion in Station Météo. Their original bytes are preserved. No third-party license is inferred or assigned to these supplied assets.

`frontend/landscape.svg` is the original Station Météo landscape from version 0.2.2. The fallback compass and arrow SVG assets reproduce the integration’s original design with the requested extended arrow.

Microsoft Fluent Emoji weather assets and the Casefabre village photograph are no longer included. Home Assistant renders its own MDI icons for controls and measurement labels. The browser test fixture contains its separate MDI license.

## Astral

Astronomical calculations use Astral 2.2 (BSD-3-Clause): https://github.com/sffjunkie/astral
The package is installed by Home Assistant; its source is not bundled here.

## Local almanac

The saint/feast calendar is adapted from the open dataset “Les saints et fêtes du calendrier”,
published by UnExtraterrestres Delespace on data.gouv.fr, updated 7 September 2024:
https://www.data.gouv.fr/datasets/les-saints-et-fetes-du-calendrier
https://static.data.gouv.fr/resources/les-saints-et-fetes-du-calendrier/20240907-201819/saints.json
Licence Ouverte / Open Licence (Etalab):
https://www.etalab.gouv.fr/licence-ouverte-open-licence/
Retrieved 15 October 2026. The adaptation keeps one saint or feast per valid calendar date,
expands abbreviations, corrects spelling/encoding and omits the erroneous June 31 record.
Names are also compared with Nominis, Conférence des évêques de France:
https://nominis.cef.fr/ical/nominis.php
This is a fixed French name-day calendar, not a year-specific movable liturgical calendar.

The 366 short daily thoughts and the 366 seasonal sayings supplied in this release
are original texts created for Station Météo. They have no invented attribution to
famous authors and are not represented as sourced traditional proverbs. They may
be customized in the integration. No text from the former online almanac is bundled
or requested by the integration.

## PyEphem

Lunar illumination and upcoming phase times use PyEphem 4.2.1 (MIT): https://rhodesmill.org/pyephem/
The package is installed by Home Assistant; its source is not bundled here.

## EUMETSAT / NASA — GeoColour

The satellite window displays runtime images from the public EUMETView WMS service:
https://view.eumetsat.int/geoserver/wms
Layer: mtg_fd:rgb_geocolour. Both EUMETSAT and NASA are credited in the viewer.
No satellite imagery is distributed with this integration.
Product information: https://view.eumetsat.int/productviewer/productDetails/mtg_fd:rgb_geocolour

## Meteociel / Météo-France / Blitzortung

Native radar frames and geographic tiles are loaded at runtime from Meteociel's
servers. Radar observations originate from Météo-France. Lightning snapshots
use Meteociel's current 30-minute observations based on the Blitzortung network.
Sources are credited in each viewer with a link to the original Meteociel page.
No Meteociel imagery, observations, website HTML or JavaScript is bundled.
The integration renders the tiles and observations with its own canvas code.
These runtime sources are used by Meteociel's website and may change.
Embedded-window and external-tab modes remain available for custom targets.

Humidity, 24-hour rain and gust maps are loaded at runtime as original PNGs.
The default satellite uses Meteociel's original Meteosat12 visible-composition
GIF animation, with its embedded dates and copyright preserved. A link to
Meteociel and the satellite data credit are shown below the map. None of these
images or animation files is included in the distribution.

## Dark theme contribution

The dark-only CSS palette is adapted from pull request #1 by stephanerosso59-debug:
https://github.com/RenaudSub/Station-Meteo/pull/1
The light theme remains the default. Theme scheduling and per-device map viewport persistence are implemented separately. The iframe sidebar patch from that PR is not included.
