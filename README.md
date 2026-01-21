# GoveeLife Home Assistant Custom Integration
This custom Home Assistant integration is a work in progress that uses the newly released API 2.0 by Govee. Feel free to contribute, all help is appreciated.

## Supported Devices 
* Lights - Light entity, color selection, dimming, effects
* Heaters - Climate, power, oscillation
* Air Purifiers - Fan entity, presets
* Fans - Fan entity, presets
* Ice Maker - power switch
* Aroma Diffuser - power switch
* Socket - power switch
* Tea Kettles - Climate, power switch

## Installing
You can install this integration with HACS or manually.
### HACS
After installing HACS ([click here for instructions](https://www.hacs.xyz/docs/use/)), add a custom repository using the steps below.
#### Add the custom repo
  - Click on the 3 dots in the top right corner.
  - Select "Custom repositories"
  - Add the URL to the repository.
  - Select the correct type.
  - Click the "ADD" button.
#### Download the Integration
  - When taken back to the HACS list, search for "goveelife"
  - In the list, click the three dots on the "goveelife" row
  - Click download
  - Choose a specific version if needed.
  - Click download
  - When complete, restart Home Assistant if needed.
More info can be found (here)[https://hacs.xyz/docs/faq/custom_repositories/] if needed.

### Manually
Copy the custom_components/goveelife to your custom_components folder. Reboot Home Assistant and configure the 'goveelife' integration via the integrations page.

### Configuration
When you add the goveelife integration, you will be prompted for an API key. To get this, you will need to:
1. Open the 'Govee Home' app on your smartphone
2. Login or create an account
3. Open the settings and tap "Apply for an API key"
4. Check your email to find the API key and use it when adding this integration to your Home Assistant instance.

Note: the integration has the option of changing the polling frequence which is how often it will hit the Govee API to check for updates. If you set this value too low, you will be rate limited and you will not be able to control your devices.

## How can YOU help?
I need API responses so I can continue to build out this integration. You can provide these resonses by opening an "issue" at the top of this repository. It's pretty simple. Use any online API query tool, and submit a GET requ
est to "https://openapi.api.govee.com/router/api/v1/user/devices". Make sure you include a single header called "Govee-API-Key" which should contain your API key aquired in your Govee app.
When you submit the reponse as an issue above, make sure you alter any MAC addresses, and DO NOT incluse your API key in the post!


For many folks setting up something like Postman or whatever to do the API call may be overkill... I'm pretty sure all Mac OSX, Linux and Windows 11 come with cURL installed by default...
curl -H 'Govee-API-Key: YOURKEYHERE' -o 'Govee API response.json' -X GET https://openapi.api.govee.com/router/api/v1/user/devices
