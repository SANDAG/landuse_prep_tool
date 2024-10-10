# 1.0 Introduction
The _conversion_sr14_sr15_ script converts Series 14 (SR14) data, used primarily in ABM2+, into Series 15 (SR15) format, which is used in ABM3. It adjusts SR14 land use and synthetic population files to match SR15 MGRA boundaries and uses an existing SR15 land use data to estimate SR15-equivalent land use columns. The exact processing procedures implemented are detailed in the following section. 

# 2.0 Methodology
## 2.1 Input Files
Table 1 lists the input files required to run the conversion script and their purpose in the process. All files must be for the same scenario year. For clarity, SR15 refers to the converted SR14 file (output of this script), while ABM3 refers to the existing ABM3 land use input file (in SR15 format) that is used in the conversion process.

**Table 1. Input Files**
|File Name|Purpose|
|---|---|
|SR14 synthetic household file|Recoded to SR 15 MGRAs and fields renamed consistent with ABM3 field names. Also summarized for household totals to be used in converted MGRA data. |
|SR14 synthetic person file| Fields renamed consistent with ABM3 field names. Summarized for person totals to be used in converted MGRA data.| 
|SR14 land use file| Source of employment and income to be used in converted MGRA data file.|
|ABM3 land use| Source of SR15 MGRAs, TAZs, acres, park space, parking costs, and a few other fields held constant in converted MGRA data.|
|MGRA SR14 to SR15 crosswalk| Crosswalk used for conversion. Created via a separate process in which the centroid of each SR14 MGRA was geocoded to the polygon of SR15 MGRAs.|

## 2.2 Data Processing
### Households and Persons 
The synthetic household and person files undergo minimal processing. For the household file, the MGRA column is updated using the SR14 to SR15 crosswalk and the column “hworkers” is renamed to “num_workers”. For the persons file, column ‘miltary’ is renamed to ‘military’, and columns ‘indcen’, ‘weeks’, ‘hours’, ‘rac1p’, ‘hisp’, and ‘version’ are removed, as they are not used in the modeling process. These files are used to calculate household and person totals in the converted SR15 land use file. 

### Land Use
The land use file undergoes extensive processing. There are three major procedures implemented depending on the columns: 
1) The converted SR14 synthetic population is used to populate household and person total columns 

2) Some ABM3 columns are maintained in the output MGRA file exactly as they are specified in the input file 

3) Some of the ABM3 columns are set based on the SR14 MGRA data file. In some cases, these are based on distributions obtained from the SR15 input data. 

It is important to note that during the conversion process values may be rounded to match the ABM3 file format, leading to some loss of accuracy and preventing the output SR15 totals from exactly matching the ABM3 totals. Table 2 below details the processing procedures and notes the columns impacted by this rounding error. Note that in the table below, we use the term “converted” to refer to data from the SR14 input file that has been converted to SR15 MGRAs using the crosswalk file. For example, the converted SR14 emp_total (total employment) field was created merging the crosswalk file with the SR14 MGRA data file, then summing emp_total by SR15 MGRA, and merging that data with the SR15 MGRAs so that SR15 MGRAs with no emp_total have a emp_total equal to 0.

**Table 2: Converted Series 15 Land Use File Fields and How They Are Calculated**
| Column Name | Calculation Procedure |
|---|---|
|mgra taz, luz_id, pseduomsa, zip09, parkactive, openspaceparkpreserve, beachactive, district27, milestocoast, acres, land_acres, effective_acres, truckregiontype, remoteAVParking, refueling_stations, MicroAccessTime, microtransit, each_dist, hch_dist, nev |Transferred over directly from the ABM3 land use file for each MGRA</p>|
|pop, hhp, gq_civ, gq_mil|Calculated based on the converted synthetic population. ‘military’ column of persons file was used to determine if a person was gq_mil. |
|hh, hh_mf, hh_sf, hh_mf| Calculated based on the converted synthetic population. ‘bldgsz’ of the households file was used to determine the type of household.|
|hhs|Calculated as hhp/hh|
|i1,i2,…,i10|ABM3 input data is used to calculate the ratio of each income column to the number of households (hh). These ratios are then used to create the new income groups in the output SR15. For example, from the ABM3 file, we calculate i1_share = i1/hh. We then multiply hh obtained from the converted synthetic population file by i1_share to calculate the final SR15 i1 values. Due to rounding errors, the sum of all income columns may not exactly equal hh in each MGRA. |
|emp_total, all employment categories| Employment categories are calculated by applying the share of an employment category at the TAZ level to the scaled SR14 employment totals, as such: <br><br><ls>1. The total employment scaling factor is calculated as follows: <br>scaling factor = sum(ABM3 emp_total) / sum(SR14 emp_total)</ls><br><br><ls> 2. SR15 emp_total = converted SR14 emp_total * scaling factor</ls><br><br><ls>3. ABM3 employment categories are aggregated to the TAZ level and the share of each employment category is calculated as: <br> ABM3_category_share = emp_category/emp_total</ls><br><br><ls> 4. The share is applied to all MGRAs in the same TAZ in the SR15 output file. SR15 emp_category = ABM3_category_share * SR15 emp_total </ls><br><br><ls> 5. Final employment values are rounded to zero decimals. </ls><br><br><ls>6. SR15 emp_total is recalculated to maintain internal consistency and correct rounding errors: SR15 emp_total = sum(all SR15 employment categories) </ls><br><br> Due to rounding errors from step 5, the sum of SR15 output emp_total does not exactly match the sum of SR15 input emp_total|
|hs, hs_sf, hs_mf, hs_mh, enrollgradekto8, enrollgrade9to12, eollegeenroll, othercollegeenroll, hotelroomtotal|Obtained by applying MGRA crosswalk and summing together rows in the same MGRA |


## 2.3 Consistency Checks
Several checks were conducted to guarantee consistency across the converted synthetic population and land use files. Specifically, we checked the following in the converted SR15 land use file:
-	Same number of MGRAs as the ABM3 land use file
-	Taz, luz_id, and other fields were unchanged from the ABM3 land use file
-	Sum of pop = total population records in synthetic population
-	Sum of hh = total household records in synthetic population

## 2.4 Output Files
The conversion script outputs three files: households, persons, and land use. All three files contain the columns necessary for running the files in ABM3. Refer to the SANDAG ABM3 documentation at https://sandag.github.io/ABM/inputs.html for more information. 

# 3.0 User Guide
To run the conversion, two files are required: 
1.	_config.yaml_ – which contains input and output directories and file names
2.	_conversion_sr14_sr15.py_ – which contains the code to convert the files 

User should clone (or download) these files to their local directory. Next, follow the steps below to convert Series 14 data to Series 15 format:  
1.	Save the input files in the directory of your choice. Input files should include: 
    - Series 14 synthetic person file
    - Series 14 synthetic household file
    - Series 14 land use file
    - ABM3 land use file
    - SR14 to SR15 MGRA crosswalk 
2.	Open the config.yaml file and update the input and output directories as well as the input and output file names. 

    ![image](images\config_pic.png)

3.	Open a terminal and navigate to the folder where conversion_sr14_sr15.py is saved.
4.	Once in the folder, type the following: **python conversion_sr14_sr15.py**
5.	When the conversion ends, the converted files will be saved in the specified output directory (line 13 of config.yaml). 



