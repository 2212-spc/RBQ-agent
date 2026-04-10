PRAGMA foreign_keys = ON;

CREATE TABLE Document_Subsets (
Document_Subset_ID INTEGER NOT NULL,
Document_Subset_Name VARCHAR(255) NOT NULL,
Document_Subset_Details VARCHAR(255) NOT NULL,
PRIMARY KEY (Document_Subset_ID)
);
CREATE TABLE Collection_Subsets (
Collection_Subset_ID INTEGER NOT NULL,
Collection_Subset_Name VARCHAR(255) NOT NULL,
Collecrtion_Subset_Details VARCHAR(255) NOT NULL,
PRIMARY KEY (Collection_Subset_ID)
);
CREATE TABLE Document_Objects (
Document_Object_ID INTEGER NOT NULL,
Parent_Document_Object_ID INTEGER,
Owner VARCHAR(255),
Description VARCHAR(255),
Other_Details VARCHAR(255),
PRIMARY KEY (Document_Object_ID)
);
CREATE TABLE Collections (
Collection_ID INTEGER NOT NULL,
Parent_Collection_ID INTEGER,
Collection_Name VARCHAR(255),
Collection_Description VARCHAR(255),
PRIMARY KEY (Collection_ID)
);
CREATE TABLE Documents_in_Collections (
Document_Object_ID INTEGER NOT NULL,
Collection_ID INTEGER NOT NULL,
PRIMARY KEY (Document_Object_ID, Collection_ID),
FOREIGN KEY (Document_Object_ID) REFERENCES Document_Objects (Document_Object_ID),
FOREIGN KEY (Collection_ID) REFERENCES Collections (Collection_ID)
);
CREATE TABLE Document_Subset_Members (
Document_Object_ID INTEGER NOT NULL,
Related_Document_Object_ID INTEGER NOT NULL,
Document_Subset_ID INTEGER NOT NULL,
PRIMARY KEY (Document_Object_ID, Related_Document_Object_ID),
FOREIGN KEY (Document_Object_ID) REFERENCES Document_Objects (Document_Object_ID),
FOREIGN KEY (Related_Document_Object_ID) REFERENCES Document_Objects
(Document_Object_ID),
FOREIGN KEY (Document_Subset_ID) REFERENCES Document_Subsets (Document_Subset_ID)
);
CREATE TABLE Collection_Subset_Members (
Collection_ID INTEGER NOT NULL,
Related_Collection_ID INTEGER NOT NULL,
Collection_Subset_ID INTEGER NOT NULL,
PRIMARY KEY (Collection_ID, Related_Collection_ID),
FOREIGN KEY (Collection_ID) REFERENCES Collections (Collection_ID),
FOREIGN KEY (Related_Collection_ID) REFERENCES Collections (Collection_ID),
FOREIGN KEY (Collection_Subset_ID) REFERENCES Collection_Subsets (Collection_Subset_ID)
);

INSERT INTO Collection_Subsets (`Collection_Subset_ID`, `Collection_Subset_Name`, `Collecrtion_Subset_Details`) VALUES (684, 'UK album', '');
INSERT INTO Collection_Subsets (`Collection_Subset_ID`, `Collection_Subset_Name`, `Collecrtion_Subset_Details`) VALUES (717, 'US album', '');
INSERT INTO Collection_Subsets (`Collection_Subset_ID`, `Collection_Subset_Name`, `Collecrtion_Subset_Details`) VALUES (741, 'Canadian album', '');
INSERT INTO Collection_Subsets (`Collection_Subset_ID`, `Collection_Subset_Name`, `Collecrtion_Subset_Details`) VALUES (813, 'History collection', '');
INSERT INTO Collection_Subsets (`Collection_Subset_ID`, `Collection_Subset_Name`, `Collecrtion_Subset_Details`) VALUES (851, 'Art collection', '');
INSERT INTO Collection_Subsets (`Collection_Subset_ID`, `Collection_Subset_Name`, `Collecrtion_Subset_Details`) VALUES (981, 'Top collection', '');
INSERT INTO Collection_Subsets (`Collection_Subset_ID`, `Collection_Subset_Name`, `Collecrtion_Subset_Details`) VALUES (997, 'Fine set', '');
INSERT INTO Collections (`Collection_ID`, `Parent_Collection_ID`, `Collection_Name`, `Collection_Description`) VALUES (6, 6, 'Best', NULL);
INSERT INTO Collections (`Collection_ID`, `Parent_Collection_ID`, `Collection_Name`, `Collection_Description`) VALUES (7, 6, 'Nice', NULL);
INSERT INTO Document_Subsets (`Document_Subset_ID`, `Document_Subset_Name`, `Document_Subset_Details`) VALUES (171, 'Best for 2000', '');
INSERT INTO Document_Subsets (`Document_Subset_ID`, `Document_Subset_Name`, `Document_Subset_Details`) VALUES (183, 'Best for 2001', '');
INSERT INTO Document_Subsets (`Document_Subset_ID`, `Document_Subset_Name`, `Document_Subset_Details`) VALUES (216, 'Best for 2002', '');
INSERT INTO Document_Subsets (`Document_Subset_ID`, `Document_Subset_Name`, `Document_Subset_Details`) VALUES (488, 'Best for 2003', '');
INSERT INTO Document_Subsets (`Document_Subset_ID`, `Document_Subset_Name`, `Document_Subset_Details`) VALUES (535, 'Best for 2004', '');
INSERT INTO Document_Subsets (`Document_Subset_ID`, `Document_Subset_Name`, `Document_Subset_Details`) VALUES (547, 'Best for 2005', '');
INSERT INTO Document_Subsets (`Document_Subset_ID`, `Document_Subset_Name`, `Document_Subset_Details`) VALUES (640, 'Best for 2006', '');
INSERT INTO Document_Subsets (`Document_Subset_ID`, `Document_Subset_Name`, `Document_Subset_Details`) VALUES (653, 'Best for 2007', '');

INSERT INTO Collection_Subset_Members (`Collection_ID`, `Related_Collection_ID`, `Collection_Subset_ID`) VALUES (6, 6, 717);
INSERT INTO Collection_Subset_Members (`Collection_ID`, `Related_Collection_ID`, `Collection_Subset_ID`) VALUES (6, 7, 981);
INSERT INTO Collection_Subset_Members (`Collection_ID`, `Related_Collection_ID`, `Collection_Subset_ID`) VALUES (7, 6, 851);
INSERT INTO Collection_Subset_Members (`Collection_ID`, `Related_Collection_ID`, `Collection_Subset_ID`) VALUES (7, 7, 851);

INSERT INTO Document_Objects (`Document_Object_ID`, `Parent_Document_Object_ID`, `Owner`, `Description`, `Other_Details`) VALUES (5, 5, 'Ransom', 'Ransom Collection', NULL);
INSERT INTO Document_Objects (`Document_Object_ID`, `Parent_Document_Object_ID`, `Owner`, `Description`, `Other_Details`) VALUES (9, 9, 'Braeden', 'Braeden Collection', NULL);
INSERT INTO Document_Objects (`Document_Object_ID`, `Parent_Document_Object_ID`, `Owner`, `Description`, `Other_Details`) VALUES (8, 9, 'Marlin', 'Marlin Collection', NULL);
INSERT INTO Document_Subset_Members (`Document_Object_ID`, `Related_Document_Object_ID`, `Document_Subset_ID`) VALUES (5, 5, 547);
INSERT INTO Document_Subset_Members (`Document_Object_ID`, `Related_Document_Object_ID`, `Document_Subset_ID`) VALUES (5, 8, 183);
INSERT INTO Document_Subset_Members (`Document_Object_ID`, `Related_Document_Object_ID`, `Document_Subset_ID`) VALUES (5, 9, 653);
INSERT INTO Document_Subset_Members (`Document_Object_ID`, `Related_Document_Object_ID`, `Document_Subset_ID`) VALUES (8, 5, 183);
INSERT INTO Document_Subset_Members (`Document_Object_ID`, `Related_Document_Object_ID`, `Document_Subset_ID`) VALUES (8, 8, 653);
INSERT INTO Document_Subset_Members (`Document_Object_ID`, `Related_Document_Object_ID`, `Document_Subset_ID`) VALUES (8, 9, 216);
INSERT INTO Document_Subset_Members (`Document_Object_ID`, `Related_Document_Object_ID`, `Document_Subset_ID`) VALUES (9, 5, 171);
INSERT INTO Document_Subset_Members (`Document_Object_ID`, `Related_Document_Object_ID`, `Document_Subset_ID`) VALUES (9, 8, 171);
INSERT INTO Documents_in_Collections (`Document_Object_ID`, `Collection_ID`) VALUES (5, 6);
INSERT INTO Documents_in_Collections (`Document_Object_ID`, `Collection_ID`) VALUES (5, 7);
INSERT INTO Documents_in_Collections (`Document_Object_ID`, `Collection_ID`) VALUES (8, 6);
INSERT INTO Documents_in_Collections (`Document_Object_ID`, `Collection_ID`) VALUES (8, 7);
INSERT INTO Documents_in_Collections (`Document_Object_ID`, `Collection_ID`) VALUES (9, 6);
INSERT INTO Documents_in_Collections (`Document_Object_ID`, `Collection_ID`) VALUES (9, 7);
