#GP Populations LSOA Ingestion file created by Donald Maruta - 28 May 24
#Quarterly publications in January, April, July and October will include Lower Layer Super Output Area (LSOA) populations
#Source ZIP file can be downloaded here https://digital.nhs.uk/data-and-information/publications/statistical/patients-registered-at-a-gp-practice

#Connect to AGOL
from arcgis.gis import GIS
gis = GIS("home")

#Import required modules
import arcpy, glob, zipfile, shutil, requests, csv, json
import pandas as pd
from zipfile import ZipFile
from arcgis.features import FeatureLayerCollection
from urllib import request

#Turn off field names table prefixes
arcpy.env.qualifiedFieldNames = False

#Set Overwrite to true
arcpy.env.overwriteOutput = True

#This creates a unique date time code for trouble shooting
todayDate = datetime.datetime.now().strftime("%y%m%d%y%H%M")

#Sets up folder variables
FGDBpath = '/arcgis/home/PracticePopulations/PracPops' + todayDate + '.gdb'
fldrPath = '/arcgis/home/PracticePopulations/'

#Create File GDB
arcpy.CreateFileGDB_management(fldrPath, 'PracPops' + todayDate + '.gdb')
tempTable = FGDBpath + "/tempTable"

#IMD2019 LSOA 2011
shpFile = '/arcgis/home/PracticePopulations/IMD2019_LSOA2011.shp'
outputShp = '/arcgis/home/PracticePopulations/PracPop.shp'

#Get PCN LookUp File
pcnXLSX = "https://fingertips.phe.org.uk/documents/epcn.xlsx"
response = requests.get(pcnXLSX)
with open("/arcgis/home/PracticePopulations/output.xlsx", "wb") as output_file:
    output_file.write(response.content)
    
#Import XLSX into FGDB
#This selects which worksheet needs to be run
worksheet_to_run = "PCN Core Partner Details"
#Import XLSX worksheetfile into GDB
arcpy.conversion.ExcelToTable("/arcgis/home/PracticePopulations/output.xlsx", tempTable, worksheet_to_run, 1) #The last variable is the row from which the column names should be taken

#Delete Expired PCNs
arcpy.management.MakeTableView(tempTable, "tempView")
arcpy.management.SelectLayerByAttribute("tempView", "NEW_SELECTION", "Practice_to_PCN_Relationship_End_Date <> '' OR Practice_Parent_Sub_ICB_Loc_Code <> '93C'")
arcpy.management.DeleteRows("tempView")

#Delete unwanted fields from XLSX
kpFlds = ["Partner_Organisation_Code", "PCN_Code", "PCN_Name"]
arcpy.management.DeleteField(tempTable, kpFlds, "KEEP_FIELDS")

#Get name of ZIP file - looks for a ZIP file in the arcgis/home/PracticePopulations folder starting with gp
zipFile = (glob.glob("/arcgis/home/PracticePopulations/gp*.zip"))
strFile = str(zipFile) #Creates the file locations as a string
strFile = (strFile.strip("[']")) #Removes the ['] characters
print(strFile)

#Unzip the ZIP file
with zipfile.ZipFile(strFile, "r") as zip_ref:
    zip_ref.extractall(fldrPath)
print("Done!")

#Get name of CSV file - looks for a CSV file in the arcgis/home/PracticePopulations folder with ends with 'all'
csvFile = (glob.glob("/arcgis/home/PracticePopulations/*all-2011.csv"))
strFile = str(csvFile) #Creates the file locations as a string
strFile = (strFile.strip("[']")) #Removes the ['] characters
print(strFile)

#Get GP Data from NHS Digital
#List of datasets
datasets = [
    {
        'filter': "OrganisationTypeID eq 'GPB'", #GPs
        'orderby': "geo.distance(Geocode, geography'POINT(-0.15874 51.6116)')",
        'top': 1000,
        'skip': 0,
        'count': True
    },
#Add more datasets as needed
]

#Specify the file paths where you want to save the CSV files
csv_file_paths = [
    "/arcgis/home/PracticePopulations/GPB.csv",
    #Add more file paths as needed
]

#Download the data for GPs from NHS Digital API
for dataset, csv_file_path in zip(datasets, csv_file_paths):
    response = requests.request(
        method='POST',
        url='https://api.nhs.uk/service-search/search?api-version=1',
        headers={
            'Content-Type': 'application/json',
            'subscription-key': '557d555fd712449f894e78e50a460000'
        },
        json=dataset
    )

    #Parse the response as JSON
    data = response.json()

    #Extract the required data from the JSON response
    output = []
    for item in data.get('value', []):
        output.append([
            item.get('OrganisationID'),
            item.get('NACSCode'),
            item.get('OrganisationName'),
            item.get('Postcode'),
            item.get('Latitude'),
            item.get('Longitude'),
            item.get('Contacts'),
            item.get('LastUpdatedDate'),
        ])

    #Open the CSV file in write mode
    with open(csv_file_path, 'w', newline='') as csvfile:
        #Create a CSV writer object
        csv_writer = csv.writer(csvfile)

        #Write the header row
        csv_writer.writerow(['OrganisationID', 'OCS_Code', 'OrganisationName', 'Postcode', 'Latitude', 'Longitude', 'Contacts', 'LastUpdatedDate'])

        #Write the output to the CSV file
        csv_writer.writerows(output)

    #Confirmation message
    print(f"Output saved as CSV: {csv_file_path}")

    #Load the CSV file into a pandas DataFrame
    df = pd.read_csv(csv_file_path, encoding = "cp1252")

    #Create a new column to store the extracted phone numbers
    df['PhoneNumber'] = ""

    #Iterate through each row in the DataFrame
    for index, row in df.iterrows():
        contacts_data = row['Contacts']
    
        #Check if the value is NaN (not a string)
        if isinstance(contacts_data, str):
            #Parse the JSON data
            parsed_data = json.loads(contacts_data)

            #Extract the telephone number
            telephone_number = parsed_data[0]["OrganisationContactValue"]

            #Update the "PhoneNumber" column with the extracted telephone number
            df.at[index, 'PhoneNumber'] = telephone_number

    #Drop the original "Contacts" column
    df.drop(columns=['Contacts'], inplace=True)

    #Save the modified DataFrame back to a CSV file
    df.to_csv(csv_file_path, index=False)

#Confirmation message
print("All datasets processed successfully.")

#Import CSV File into FGDB
arcpy.conversion.TableToGeodatabase(strFile, FGDBpath)

#Import GBP File into FGDB
arcpy.conversion.TableToGeodatabase("/arcgis/home/PracticePopulations/GPB.csv", FGDBpath)

#Get name of Table in FGDB
arcpy.env.workspace = FGDBpath
orgTab = arcpy.ListTables()
orgTab = orgTab[1]
print(orgTab)

#Join Import Table with GPB Data
tempdata = arcpy.management.AddJoin("GPB", "OCS_Code", orgTab, "PRACTICE_CODE")
arcpy.management.CopyRows(tempdata, "GPData")

#Delete Unneeded Fields
keepMe = ["OrganisationID", "OCS_Code", "OrganisationName", "Postcode", "Latitude", "Longitude", "LastUpdatedDate", "PhoneNumber"]
arcpy.management.DeleteField("GPData", keepMe, "KEEP_FIELDS")

#Delete Duplicate Features
arcpy.management.DeleteIdentical("GPData", "OCS_Code")

#Add PCN_Code & PCN_Name column
tempdata = arcpy.management.AddJoin("GPData", "OCS_CODE", tempTable, "Partner_Organisation_Code", "KEEP_COMMON")
arcpy.management.CopyRows(tempdata, "GPData2")

#Delete unwanted columns
deleteMe = ["Partner_Organisation_Code", "OBJECTID_1"]
arcpy.management.DeleteField("GPData2", deleteMe)

#Add Borough Column
#Import PostCodeBoroughLookup File into FGDB
arcpy.conversion.TableToGeodatabase("/arcgis/home/PracticePopulations/PostCodeBoroughLookup.csv", FGDBpath)
tempdata = arcpy.management.AddJoin("GPData2", "Postcode", "PostCodeBoroughLookup", "PostCode")
arcpy.management.CopyRows(tempdata, "GPData2a")
deleteMe = ["OBJECTID_1", "PostCode_1"]
arcpy.management.DeleteField("GPData2a", deleteMe)

#Export GDB Table to CSV
arcpy.conversion.ExportTable("GPData2a", "GPData.csv")

#GPData #Completed

#Add NUMBER OF PATIENTS column
tempdata = arcpy.management.AddJoin("GPData2a", "OCS_Code", orgTab, "PRACTICE_CODE", "KEEP_COMMON")
arcpy.management.CopyRows(tempdata, "GPData3")
#Delete Unrequired Columns
deleteMe = ["OBJECTID_1", "PUBLICATION", "EXTRACT_DATE_X", "EXTRACT_DATE_Y", "PRACTICE_CODE", "PRACTICE_CODE_X", "PRACTICE_CODE_Y", "PRACTICE_NAME"]
arcpy.management.DeleteField("GPData3", deleteMe)

#Remove Non NCL ICB LSOAs
arcpy.conversion.TableToGeodatabase("/arcgis/home/PracticePopulations/IMD2019_LSOA2011.dbf", FGDBpath)
#Delete Unneeded Fields
keepMe = ["Borough", "lsoa11cd"]
arcpy.management.DeleteField("IMD2019_LSOA2011", keepMe, "KEEP_FIELDS")
tempdata = arcpy.management.AddJoin("GPData3", "LSOA_CODE", "IMD2019_LSOA2011", "lsoa11cd", "KEEP_COMMON")
arcpy.management.CopyRows(tempdata, "GPData4")
#Delete Unneeded Fields
deleteMe = ["OBJECTID_1", "lsoa11cd"]
arcpy.management.DeleteField("GPData4", deleteMe)
#Delete IMD2019_LSOA2011 Table
arcpy.management.Delete("IMD2019_LSOA2011")

#Add New Field to Join LSOA & PCN
exp = "!LSOA_CODE! + !PCN_Code!"
arcpy.management.CalculateField("GPData4", "LSOA_PCN", exp)

#Create a new field for the sum of patients by Practice
arcpy.analysis.Statistics("GPData4", "tempSum", [["NUMBER_OF_PATIENTS", "SUM"]], "OCS_Code")
#Create a new field for the sum of patients by PCN
arcpy.analysis.Statistics("GPData4", "tempSum2", [["NUMBER_OF_PATIENTS", "SUM"]], "PCN_Code")
#Create a new field for the sum of patients by LSOA and PCN
arcpy.analysis.Statistics("GPData4", "tempSum3", [["NUMBER_OF_PATIENTS", "SUM"]], [["LSOA_PCN"]])
#Create a new field for the sum of patients by LSOA
arcpy.analysis.Statistics("GPData4", "tempSum4", [["NUMBER_OF_PATIENTS", "SUM"]], [["LSOA_CODE"]])

#Join the sum of patients by Practice to the main Table
tempdata = arcpy.management.AddJoin("GPData4", "OCS_Code", "tempSum", "OCS_Code", "KEEP_COMMON")
arcpy.management.CopyRows(tempdata, "GPData5")
#Join the sum of patients by PCN to the main Table
tempdata = arcpy.management.AddJoin("GPData5", "PCN_Code", "tempSum2", "PCN_Code", "KEEP_COMMON")
arcpy.management.CopyRows(tempdata, "GPData6")
#Join the sum of patients by LSOA and PCN to the main Table
tempdata = arcpy.management.AddJoin("GPData6", "LSOA_PCN", "tempSum3", "LSOA_PCN", "KEEP_COMMON")
arcpy.management.CopyRows(tempdata, "GPData7")
#Join the sum of patients by LSOA to the main Table
tempdata = arcpy.management.AddJoin("GPData7", "LSOA_CODE", "tempSum4", "LSOA_CODE", "KEEP_COMMON")
arcpy.management.CopyRows(tempdata, "GPData8")

#Rename Columns for Totals
arcpy.management.AlterField("GPData8", "SUM_NUMBER_OF_PATIENTS", "TOTAL_GP", "TOTAL_GP")
arcpy.management.AlterField("GPData8", "SUM_NUMBER_OF_PATIENTS_1", "TOTAL_PCN", "TOTAL_PCN")
arcpy.management.AlterField("GPData8", "SUM_NUMBER_OF_PATIENTS_12", "TOTAL_LSOA_PCN", "TOTAL_LSOA_PCN")
arcpy.management.AlterField("GPData8", "SUM_NUMBER_OF_PATIENTS_12_13", "TOTAL_LSOA", "TOTAL_LSOA")

#Delete Unrequired Columns
deleteMe = ["OBJECTID_1", "OCS_Code_1", "FREQUENCY", "OBJECTID_12", "PCN_Code_1", "FREQUENCY_1", "LSOA_PCN_1", "FREQUENCY_12", "OBJECTID_12_13", "LSOA_CODE_1", "OBJECTID_12_13_14", "FREQUENCY_12_13"]
arcpy.management.DeleteField("GPData8", deleteMe)

#Calculate Percentage Field for Practice (NUMBER OF PATIENTS / SUM NUMBER OF PATIENTS)
exp = "!NUMBER_OF_PATIENTS! / !TOTAL_GP! * 100"
arcpy.management.CalculateField("GPData8", "GP_PERCENTAGE", exp, field_type = "FLOAT")
#Calculate Percentage Field for PCN (GP NUMBER OF PATIENTS / PCN SUM NUMBER OF PATIENTS)
exp = "!NUMBER_OF_PATIENTS! / !TOTAL_PCN! * 100"
arcpy.management.CalculateField("GPData8", "PCN_PERCENTAGE", exp, field_type = "FLOAT")
#Calculate Percentage Field for PCN & LSOA
exp = "!NUMBER_OF_PATIENTS! / !TOTAL_LSOA_PCN! * 100"
arcpy.management.CalculateField("GPData8", "PCN_LSOA_PC", exp, field_type = "FLOAT")
#Calculate Percentage Field for LSOA
exp = "!NUMBER_OF_PATIENTS! / !TOTAL_LSOA! * 100"
arcpy.management.CalculateField("GPData8", "LSOA_PC", exp, field_type = "FLOAT")

#Create list of PCNs within NCL ICB
arcpy.management.CopyRows("GPData8", "GPData9")
#Delete all fields except PCN_Code
arcpy.management.DeleteField("GPData9", ["PCN_Code", "PCN_Name", "Borough"], "KEEP_FIELDS")
#Delete Duplicate Features
arcpy.management.DeleteIdentical("GPData9", "PCN_Code")

#Convert DF field into list
columns = ["PCN_Code", "PCN_Name", "Borough"]
df = pd.DataFrame(data=arcpy.da.SearchCursor("GPData9", columns), columns=columns)
my_field_list = df["PCN_Code"].to_list()
print(my_field_list)
lengthFdLst = len(my_field_list)

#Import SHP File into FGDB
arcpy.conversion.FeatureClassToGeodatabase(shpFile, FGDBpath)

for i in range(lengthFdLst):
    #Select Data by PCN
    PCNs2Run = my_field_list[i]
    outPCN = "PCN_" + PCNs2Run
    sqlExp = f'"PCN_Code" = \'{PCNs2Run}\''
    tempTest = arcpy.management.SelectLayerByAttribute("GPData8", "NEW_SELECTION", sqlExp)
    arcpy.management.CopyRows(tempTest, outPCN)
    #Remove Duplicate Features
    delFlds = ["LSOA_CODE", "TOTAL_LSOA_PCN"]
    arcpy.management.DeleteIdentical(outPCN, delFlds)
    #Delete unneeded fields
    kpFlds = ["PCN_Code", "PCN_Name", "LSOA_CODE", "TOTAL_LSOA_PCN", "Borough"]
    arcpy.management.DeleteField(outPCN, kpFlds, "KEEP_FIELDS")
    #Make field values descending from largest to smallest
    arcpy.management.Sort(outPCN, "TempDesc", [["TOTAL_LSOA_PCN", "DESCENDING"]])
    #Get overall total for totals column
    arcpy.analysis.Statistics(outPCN, "TempTot", [["TOTAL_LSOA_PCN", "SUM"]])
    #Convert TempTot into NumPy then Pandas DF
    arr = arcpy.da.TableToNumPyArray("TempTot", '*')
    #convert TempTot to a Pandas DataFrame
    df = pd.DataFrame(arr)
    #Get total value from DF
    val = df.iat[0, 2]
    #Create 75% value of Total - Change Percentage here if required
    PC = 0.75 #Change this value to change percentage if required
    reqPC = PC * val
    #Convert TempDesc into NumPy then Pandas DF
    arr = arcpy.da.TableToNumPyArray("TempDesc", '*')
    #convert TempDesc to a Pandas DataFrame
    df = pd.DataFrame(arr)
    #Loops through the values in tabe TempDesc in order to find which LSOAs belong in the top 75% of the PCN population
    len = df.shape[0]
    runTot = 0
    for i in range (len):
        tot = df.iat[i,5]
        runTot = runTot + tot
        #Checks if the running total is greater than the required total and breaks the loop if so
        if runTot > reqPC:
            print(i)
            break
    #Delete unneeded records
    df = df.drop(df[df['OBJECTID'] > i+1].index)
    #Delete unneeded columns
    #df = df.drop(df.columns[[0, 3]], axis=1)  #df.columns is zero-based pd.Index
    #Export Pandas Dataframe to CSV
    df.to_csv(fldrPath + outPCN + ".csv", index=False)
    #Import CSV to FGDB
    arcpy.conversion.TableToGeodatabase(fldrPath + outPCN + ".csv", FGDBpath)
    #Join Table to LSOA FC
    tempdata = arcpy.management.AddJoin("IMD2019_LSOA2011", "LSOA11CD", outPCN, "LSOA_CODE", "KEEP_COMMON")
    arcpy.management.CopyFeatures(tempdata, r"memory\FC")
    #Dissolve all the LSOAs into one large area
    arcpy.analysis.PairwiseDissolve(r"memory\FC", r"memory\FC_Dis", ["PCN_Code", "PCN_Name", "Borough"])
    #Smooth the polygon
    arcpy.cartography.SmoothPolygon(r"memory\FC_Dis", outPCN + "FC_SP", "PAEK", 1500)

#Merge All FCs
AllFCs = arcpy.ListFeatureClasses("*FC_SP")
print(AllFCs)
arcpy.management.Merge(AllFCs, "AllFCs", "", "ADD_SOURCE_INFO")

#Delete Unwanted Fields
arcpy.management.DeleteField("AllFCs", ["PCN_Code", "PCN_Name", "Borough"], "KEEP_FIELDS")

#Export All FCs to Shapefile
arcpy.conversion.FeatureClassToShapefile("AllFCs", fldrPath)

#List of files in complete directory
finalName = "AllFCs"
file_list = [finalName + ".shp", finalName + ".shx", finalName + ".dbf", finalName + ".prj"]
os.chdir(fldrPath)
#Create Zip file
shpzip = finalName + ".zip"
with zipfile.ZipFile(shpzip, 'w') as zipF:
    for file in file_list:
        zipF.write(file, compress_type=zipfile.ZIP_DEFLATED)

#PCNs #Completed

#Join the sum of patients by Practice to the main Table
tempdata = arcpy.management.AddJoin("IMD2019_LSOA2011", "LSOA11CD", "GPData8", "LSOA_CODE")
arcpy.management.CopyFeatures(tempdata, "GPDataFC")


#In[33]:


#Delete unrequired fields
deleteMe = ["LSOA_CODE", "OBJECTID_1", "LSOA_PCN", "Borough_1"]
arcpy.management.DeleteField("GPDataFC", deleteMe)

#Export the FC to a SHP
arcpy.management.Rename("GPDataFC", "PracPop")
arcpy.conversion.FeatureClassToShapefile("PracPop", fldrPath)

#List of files in complete directory
finalName2 = "PracPop"
file_list2 = [finalName2 + ".shp", finalName2 + ".shx", finalName2 + ".dbf", finalName2 + ".prj"]
os.chdir(fldrPath)

#Create Zip file
shpzip2 = finalName2 + ".zip"
with zipfile.ZipFile(shpzip2, 'w') as zipF:
    for file in file_list2:
        zipF.write(file, compress_type=zipfile.ZIP_DEFLATED)

#LSOAs #Completed

#Create 75% Coverage Diagrams for GPs
#Convert DF field into list
arcpy.env.workspace = FGDBpath
columns = ["OCS_CODE", "OrganisationName", "PCN_Code"]
df = pd.DataFrame(data=arcpy.da.SearchCursor("GPData2", columns), columns=columns)
my_field_list = df["OCS_CODE"].to_list()
my_field_list = list(set(my_field_list))
print(my_field_list)
lengthFdLst = len(my_field_list)

for i in range(lengthFdLst):
#for i in range(2):
    #Select Data by PCN
    GPs2Run = my_field_list[i]
    outGP = "GP_" + GPs2Run
    sqlExp = f'"OCS_Code" = \'{GPs2Run}\''
    tempTest = arcpy.management.SelectLayerByAttribute("GPData7", "NEW_SELECTION", sqlExp)
    arcpy.management.CopyRows(tempTest, outGP)
    #Remove Duplicate Features
    #delFlds = ["LSOA_CODE", "SUM_NUMBER_OF_PATIENTS_12"]
    #arcpy.management.DeleteIdentical(outGP, delFlds)
    #Delete unneeded fields
    kpFlds = ["OCS_CODE", "OrganisationName", "PCN_Code", "LSOA_CODE", "NUMBER_OF_PATIENTS"]
    arcpy.management.DeleteField(outGP, kpFlds, "KEEP_FIELDS")
    #Make field values descending from largest to smallest
    arcpy.management.Sort(outGP, "TempDesc", [["NUMBER_OF_PATIENTS", "DESCENDING"]])
    #Get overall total for totals column
    arcpy.analysis.Statistics(outGP, "TempTot", [["NUMBER_OF_PATIENTS", "SUM"]])
    #Convert TempTot into NumPy then Pandas DF
    arr = arcpy.da.TableToNumPyArray("TempTot", '*')
    #convert TempTot to a Pandas DataFrame
    df = pd.DataFrame(arr)
    #Get total value from DF
    val = df.iat[0, 2]
    #Create 75% value of Total - Change Percentage here if required
    PC = 0.75 #Change this value to change percentage if required
    reqPC = PC * val
    #Convert TempDesc into NumPy then Pandas DF
    arr = arcpy.da.TableToNumPyArray("TempDesc", '*')
    #convert TempDesc to a Pandas DataFrame
    df = pd.DataFrame(arr)
    #Loops through the values in tabe TempDesc in order to find which LSOAs belong in the top 75% of the PCN population
    len = df.shape[0]
    runTot = 0
    for i in range (len):
        tot = df.iat[i,5]
        runTot = runTot + tot
        #Checks if the running total is greater than the required total and breaks the loop if so
        if runTot > reqPC:
            print(i)
            break
    #Delete unneeded records
    df = df.drop(df[df['OBJECTID'] > i+1].index)
    #Delete unneeded columns
    #df = df.drop(df.columns[[0, 3]], axis=1)  #df.columns is zero-based pd.Index
    #Export Pandas Dataframe to CSV
    df.to_csv(fldrPath + outGP + ".csv", index=False)
    #Import CSV to FGDB
    arcpy.conversion.TableToGeodatabase(fldrPath + outGP + ".csv", FGDBpath)
    #Join Table to LSOA FC
    tempdata = arcpy.management.AddJoin("IMD2019_LSOA2011", "LSOA11CD", outGP, "LSOA_CODE", "KEEP_COMMON")
    arcpy.management.CopyFeatures(tempdata, r"memory\FC")
    #Dissolve all the LSOAs into one large area
    arcpy.analysis.PairwiseDissolve(r"memory\FC", r"memory\FC_Dis", ["OCS_CODE", "OrganisationName", "PCN_Code"])
    #Smooth the polygon
    arcpy.cartography.SmoothPolygon(r"memory\FC_Dis", outGP + "GP_SP", "PAEK", 1500)

#Get the LSOA with the highest number and percentages
arcpy.management.CopyFeatures("PracPop", "PracPopTop")
keepMe = ["lsoa11cd", "lsoa11nm", "Borough", "PCN_Code", "PCN_Name", "TOTAL_LSOA_PCN", "TOTAL_LSOA"]
arcpy.management.DeleteField("PracPopTop", keepMe, "KEEP_FIELDS")
arcpy.management.DeleteIdentical("PracPopTop", ["lsoa11cd", "PCN_Code"])
sqlExp = "!TOTAL_LSOA_PCN! / !TOTAL_LSOA! * 100"
arcpy.management.CalculateField("PracPopTop", "CurPC", sqlExp, field_type="FLOAT")
arcpy.conversion.ExportTable("PracPopTop", "PracPopTop.csv")
arcpy.management.Sort("PracPopTop", "PracPopTopDesc", [["CurPC", "DESCENDING"]])
arcpy.management.DeleteIdentical("PracPopTopDesc", "lsoa11cd")
arcpy.conversion.ExportTable("PracPopTopDesc", "PracPopTopDesc.csv")

#Create Dataframe
def second_largest(l = []):    
    return (l.nlargest(3).min())
def third_largest(l = []):    
    return (l.nlargest(5).min())
#Define a function to get the index of the second highest value
def get_second_max_idx(row, columns):
    #Get the values for the row across the specified columns
    values = row[columns]
    if len(values) < 2:
        return np.nan  #Not enough values to determine the second highest
    #Sort values in descending order and get the index of the second highest value
    sorted_idx = values.sort_values(ascending=False).index
    return sorted_idx[1]  #Return the column name of the second highest value
def get_third_max_idx(row, columns):
    #Get the values for the row across the specified columns
    values = row[columns]
    if len(values) < 3:
        return np.nan  #Not enough values to determine the second highest
    #Sort values in descending order and get the index of the second highest value
    sorted_idx = values.sort_values(ascending=False).index
    return sorted_idx[2]  #Return the column name of the second highest value
os.chdir(fldrPath)
df = pd.read_csv("/arcgis/home/PracticePopulations/PracPopTop.csv")
table = pd.pivot_table(df, values='CurPC', index=['lsoa11cd', 'lsoa11nm', 'Borough'],
                       columns=['PCN_Name'])
pcn_columns = [col for col in table.columns if 'PCN' in col]
table[pcn_columns] = table[pcn_columns].apply(pd.to_numeric, errors='coerce')
table['Maximum'] = table.max(axis=1)
table['Max2'] = table.apply(second_largest, axis = 1)
table['Max3'] = table.apply(third_largest, axis = 1)
#table.loc[table['Maximum'] > table['Max2']*1.5, 'Max_PCN'] = table.loc[:,'Maximum']
print(pcn_columns)
table.loc[table['Maximum'] > table['Max2']*1.5, 'Max_PCN'] = table.loc[:, pcn_columns].idxmax(axis=1)
table.loc[table['Maximum'] < table['Max2']*1.5, 'Max_PCN2'] = table.loc[:, pcn_columns].idxmax(axis=1)
table.loc[table['Maximum'] < table['Max2']*1.5, 'Max_PCN3'] = table.loc[
    table['Maximum'] < table['Max2']*1.5
].apply(lambda row: get_second_max_idx(row, pcn_columns), axis=1)
table.loc[(table['Max2'] < table['Max3']*1.5) & (table['Max_PCN'].isnull()), 'Max_PCN4'] = table.loc[
    table['Max2'] < table['Max3']*1.5
].apply(lambda row: get_third_max_idx(row, pcn_columns), axis=1)
table.to_csv('PracPopTopAll2.csv')
arcpy.conversion.TableToGeodatabase('/arcgis/home/PracticePopulations/PracPopTopAll2.csv', FGDBpath)
tempdata = arcpy.management.AddJoin("IMD2019_LSOA2011", "LSOA11CD", "PracPopTopAll2", "lsoa11cd")
arcpy.management.CopyFeatures(tempdata, "PracPopTopAll")
arcpy.conversion.FeatureClassToShapefile("PracPopTopAll", fldrPath)

#List of files in complete directory
finalName5 = "PracPopTopAll"
file_list5 = [finalName5 + ".shp", finalName5 + ".shx", finalName5 + ".dbf", finalName5 + ".prj"]
os.chdir(fldrPath)

#Create Zip file
shpzip5 = finalName5 + ".zip"
with zipfile.ZipFile(shpzip5, 'w') as zipF:
    for file in file_list5:
        zipF.write(file, compress_type=zipfile.ZIP_DEFLATED)

arcpy.conversion.FeatureClassToShapefile("PracPopTopDesc", fldrPath)


#In[ ]:


#List of files in complete directory
finalName4 = "PracPopTopDesc"
file_list4 = [finalName4 + ".shp", finalName4 + ".shx", finalName4 + ".dbf", finalName4 + ".prj"]
os.chdir(fldrPath)

#Create Zip file
shpzip4 = finalName4 + ".zip"
with zipfile.ZipFile(shpzip4, 'w') as zipF:
    for file in file_list4:
        zipF.write(file, compress_type=zipfile.ZIP_DEFLATED)

#Initial Publish PCN Coverages to AGOL
#item = gis.content.add({}, shpzip)
#published_item = item.publish()
#published_item.share(everyone=True)

#Initial Publish PracPop LSOAs to AGOL
#item = gis.content.add({}, shpzip2)
#published_item = item.publish()
#published_item.share(everyone=True)

#Initial Publish PracPop Top to AGOL
#item = gis.content.add({}, shpzip4)
#published_item = item.publish()
#published_item.share(everyone=True)

#Initial Publish PracPop Top All to AGOL
item = gis.content.add({}, shpzip5)
published_item = item.publish()
published_item.share(everyone=True)

#Overwrite the existing service - PracPopTopAll LSOAs
feat_id = 'dbed740abdd84192a48ab74fe359da0b'
item = gis.content.get(feat_id)
item_collection = FeatureLayerCollection.fromitem(item)
#call the overwrite() method which can be accessed using the manager property
item_collection.manager.overwrite('/arcgis/home/PracticePopulations/PracPopTopAll.zip')
item.share(everyone=True)
update_dict = {"capabilities": "Query,Extract"}
item_collection.manager.update_definition(update_dict)
item.content_status="authoritative"

#Initial Publish GPs to AGOL
#my_csv = ("/arcgis/home/PracticePopulations/GPData.csv")
#item_prop = {'title':'GPData2'}
#csv_item = gis.content.add(item_properties=item_prop, data=my_csv)
#params={"type": "csv", "locationType": "coordinates", "latitudeFieldName": "Latitude", "longitudeFieldName": "Longitude"}
#csv_item.publish(publish_parameters=params)
#csv_item.publish(overwrite = True)

#Overwrite the existing service - PCN Coverages
feat_id = 'eadf805a60604f268c239cdd5a2f9b62'
item = gis.content.get(feat_id)
item_collection = FeatureLayerCollection.fromitem(item)
#call the overwrite() method which can be accessed using the manager property
item_collection.manager.overwrite('/arcgis/home/PracticePopulations/AllFCs.zip')
item.share(everyone=True)
update_dict = {"capabilities": "Query,Extract"}
item_collection.manager.update_definition(update_dict)
item.content_status="authoritative"

#Overwrite the existing service - PracPopTop LSOAs
feat_id = '6eb1029dea40478087c7b7fbfab1a3f2'
item = gis.content.get(feat_id)
item_collection = FeatureLayerCollection.fromitem(item)
#call the overwrite() method which can be accessed using the manager property
item_collection.manager.overwrite('/arcgis/home/PracticePopulations/PracPopTopDesc.zip')
item.share(everyone=True)
update_dict = {"capabilities": "Query,Extract"}
item_collection.manager.update_definition(update_dict)
item.content_status="authoritative"

#Overwrite the existing service - PracPop LSOAs
feat_id = 'd75f3b93c50a4d8d87a00ce303d712ca'
item = gis.content.get(feat_id)
item_collection = FeatureLayerCollection.fromitem(item)
#call the overwrite() method which can be accessed using the manager property
item_collection.manager.overwrite('/arcgis/home/PracticePopulations/PracPop.zip')
item.share(everyone=True)
update_dict = {"capabilities": "Query,Extract"}
item_collection.manager.update_definition(update_dict)
item.content_status="authoritative"

#Overwrite the existing service - GPData
feat_id = 'cfb7f847d14b42cebfe28b99590ddf00'
item = gis.content.get(feat_id)
item_collection = FeatureLayerCollection.fromitem(item)
#call the overwrite() method which can be accessed using the manager property
item_collection.manager.overwrite('/arcgis/home/PracticePopulations/GPData.csv')
#arcpy.management.DeleteRows(item)
item.share(everyone=True)
update_dict = {"capabilities": "Query,Extract"}
item_collection.manager.update_definition(update_dict)
item.content_status="authoritative"

#Code to delete unnecessary files

#Get a list of all subdirectories (folders) in the specified folder
folders = [f for f in os.listdir(fldrPath) if os.path.isdir(os.path.join(fldrPath, f))]

for folder in folders:
    folder = os.path.join(fldrPath, folder)
    shutil.rmtree(folder)

#List of files to preserve
files_to_preserve = ["IMD2019_LSOA2011.dbf", "IMD2019_LSOA2011.prj", "IMD2019_LSOA2011.shp", "IMD2019_LSOA2011.shx", "IMD2019_LSOA2011.zip", "PostCodeBoroughLookUp.csv"]

#Get a list of all files in the directory
all_files = glob.glob(os.path.join(fldrPath, "*"))

#Iterate over each file
for file_path in all_files:
    #Get the file name
    file_name = os.path.basename(file_path)
    #Check if the file name is not in the list of files to preserve
    if file_name not in files_to_preserve:
        #Delete the file
        os.remove(file_path)
        print(f"Deleted {file_name}")

print("All files except the specified ones have been deleted.")
