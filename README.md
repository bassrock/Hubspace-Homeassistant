Please ask support questions in homeassistant forums: <https://community.home-assistant.io/t/new-hubspace-integration>

### Device Support

This version of the Hubspace respository has been tested against the following devices:

* Home Decorators Collection Fans (Ones with Color Temp, Direction, and Brightness)
* Defiant Outdoor Plug (HPPA52CWBA023)
* Commercial Electric Light Switch

As long as HubSpace reports the correct device type that matches the aboves type of devices, it should work with this integration.

### Information

This integration works by polling the HubSpace API every 60 seconds. It will only do 1 request to update all the devices on the account using HomeAssistants built in platform based polling.

### Installation

Preferred method: Add this repo as a custom repository in [HACS](https://hacs.xyz/). Add the hubspace integration.

Clicking this badge should add the repo for you:
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bassrock&repository=Hubspace-Homeassistant&category=integration)

Manually add repo:
Adding a custom repo directions `https://hacs.xyz/docs/faq/custom_repositories/`  
Use the custom repo link `https://github.com/bassrock/Hubspace-Homeassistant`
Select the category type `integration`  
Then once it's there (still in HACS) click the INSTALL button  

Manual method: copy the hubspace/ folder in the repo to `<config_dir>/custom_components/hubspace/`.

### Support for a new model

Please make a github issue if you want support for a new model. You will need to provide test data so that I can code against it. Of course, PRs are always welcome as well.

Easiest way to help is to download the Testhubspace.py (<https://raw.githubusercontent.com/jdeath/Hubspace-Homeassistant/main/TestHubspace.py>) and run it (may need to run `pip install requests` first). It will prompt you for your hubspace username and password. It will output data, which you should copy and paste into the GitHub issue. The output has been anonymized, personal information has been removed or randomized.

[![Star History Chart](https://api.star-history.com/svg?repos=bassrock/Hubspace-Homeassistant&type=Date)](https://star-history.com/#jdeath/Hubspace-Homeassistant&Date)

## Acknowledgements

This repository was built from the original by @jdeath at <https://github.com/jdeath/Hubspace-Homeassistant> and adapted with code from @mecolmg <https://github.com/mecolmg/Hubspace-Homeassistant>. I could not have done this without their original codebases. And would be happy to merge them all back together in favor of 1 version of the repo.
