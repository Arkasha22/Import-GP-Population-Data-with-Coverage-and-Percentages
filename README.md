# Import-GP-Population-Data-with-Coverage-and-Percentages

This allows users to import GP population data, create 75% population and PCN coverage diagrams, and exports data to WMS format.

Python code designed to be run in ArcGIS OnLine Notebook

It carries out the following actions in the following order
 - Connect to AGOL
 - Import required modules
 - Sets up folder variables
 - Create File GDB
 - Get PCN LookUp File
 - Import XLSX into FGDB
 - Delete Expired PCNs
 - Delete unwanted fields from XLSX
 - Get name of ZIP file - looks for a ZIP file in the arcgis/home/PracticePopulations folder starting with gp
 - Get name of CSV file - looks for a CSV file in the arcgis/home/PracticePopulations folder with ends with 'all'
 - Download the data for GPs from NHS Digital API
 - Join Import Table with GPB Data
 - Delete Unneeded Fields
 - Delete Duplicate Features
 - Add PCN_Code & PCN_Name column
 - Import PostCodeBoroughLookup File into FGDB
 - Add NUMBER OF PATIENTS column
 - Remove Non NCL ICB LSOAs
 - Add New Field to Join LSOA & PCN
 - Create a new field for the sum of patients by Practice, PCN, LSOA, LSOA & PCN
 - Rename Columns for Totals
 - Calculate Percentage Field for Practice (NUMBER OF PATIENTS / SUM NUMBER OF PATIENTS)
 - Calculate Percentage Field for PCN (GP NUMBER OF PATIENTS / PCN SUM NUMBER OF PATIENTS)
 - Calculate Percentage Field for PCN & LSOA
 - Calculate Percentage Field for LSOA
 - Create list of PCNs within NCL ICB
 - Import SHP File into FGDB
 - Join the sum of patients by Practice to the main Table
 - Create 75% Coverage Diagrams for GPs
 - Get the LSOA with the highest number and percentages
 - Define 2nd largest function
 - Define 3rd largest function
 - Initial Publish PCN Coverages to AGOL
 - Initial Publish PracPop LSOAs to AGOL
 - Initial Publish PracPop Top to AGOL
 - Initial Publish PracPop Top All to AGOL
 - Overwrite the existing service - PracPopTopAll LSOAs
 - Initial Publish GPs to AGOL
 - Overwrite the existing service - PCN Coverages
 - Overwrite the existing service - PracPopTop LSOAs
 - Overwrite the existing service - PracPop LSOAs
 - Overwrite the existing service - GPData
 - Code to delete unnecessary files
