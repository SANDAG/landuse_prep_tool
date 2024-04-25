# landuse_prep_tool
This script prepares land use and synthentic population files for ABM3 Model input, received from E&amp;F for ABM including auxiliary data(School district and AV data), MicroMobility, MicroTransit, Parking

<hr>

## Steps to Run
- Make sure config files are setup pointing to correct E&amp;F directory, other input directory and output directory. Also verify the scenario year.
- First parking data is created by estimating spaces, creating districts and finally estimating costs. All parameters for this are setup in config.yaml file.
- Similarly check if a new parking policy is to be implemented and add its policy type, policy rates csv & rates update %

## Parking Policy setup
- By default the policy implementation is False.
- Two types of policy can be used: 
    - PCA - Focuses on particular Parking Constrained Areas (PCA)
    - Mobility Hubs - Considered all the MGRAs in Mobility Hubs
- Parking Policy is defined by Mobility Hub name with new prices for a particular year. They would be mapped based on type of policy defined in earlier step.
- Parking rate update value is defined to increase or decrease the rates given in the Policy. Useful for sentivity testing.
