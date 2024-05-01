# GoveeLife Home Assistant Custom Integration
This custom Home Assistant integration is a work in progress that uses the newly released API 2.0 by Govee. Feel free to contribute, all help is appreciated.

## Supported Devices 
* All lights - Light entity
* Heaters - Climate, power, oscillation
* Air Purifiers - Fan entity
* Fans - Fan entity
* Ice Maker - power switch
* Aroma Diffuser - power switch


## How can YOU help?
I need API responses so I can continue to build out this integration. You can provide these resonses by opening an "issue" at the top of this repository. It's pretty simple. Use any online API query tool, and submit a GET requ
est to "https://openapi.api.govee.com/router/api/v1/user/devices". Make sure you include a single header called "Govee-API-Key" which should contain your API key aquired in your Govee app.
When you submit the reponse as an issue above, make sure you alter any MAC addresses, and DO NOT incluse your API key in the post!
