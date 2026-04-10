PRAGMA foreign_keys = ON;
CREATE TABLE Services (
Service_ID INTEGER NOT NULL,
Service_Details VARCHAR(255),
PRIMARY KEY (Service_ID)
);
CREATE TABLE Customers (
Customer_ID INTEGER NOT NULL,
Customer_Details VARCHAR(255) NOT NULL,
PRIMARY KEY (Customer_ID)
);
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (12, 'Amalia Johnston');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (32, 'Miss Annamarie Lowe');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (78, 'Miss Alexandra Kemmer MD');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (93, 'Agustina Stoltenberg');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (98, 'Dr. Jessyca Roob');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (103, 'Hardy Kutch');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (113, 'Vicky Keeling');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (119, 'Verdie Stehr');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (173, 'Dr. Rupert Lind');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (212, 'Flo Crooks');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (217, 'Baron Gottlieb');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (256, 'Delores Fahey');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (286, 'Sterling Spencer');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (293, 'Mr. Rollin Jakubowski');
INSERT INTO `Customers` (`Customer_ID`, `Customer_Details`) VALUES (295, 'Mr. Kraig Mohr');

CREATE TABLE Channels (
Channel_ID INTEGER NOT NULL,
Channel_Details VARCHAR(255) NOT NULL,
PRIMARY KEY (Channel_ID)
);
INSERT INTO `Channels` (`Channel_ID`, `Channel_Details`) VALUES (16, '15 ij');
INSERT INTO `Channels` (`Channel_ID`, `Channel_Details`) VALUES (45, '75 ww');
INSERT INTO `Channels` (`Channel_ID`, `Channel_Details`) VALUES (55, '92 ve');
INSERT INTO `Channels` (`Channel_ID`, `Channel_Details`) VALUES (65, '40 zy');
INSERT INTO `Channels` (`Channel_ID`, `Channel_Details`) VALUES (78, '13 ik');

INSERT INTO `Services` (`Service_ID`, `Service_Details`) VALUES (313, 'driving license');
INSERT INTO `Services` (`Service_ID`, `Service_Details`) VALUES (430, 'broker license');
INSERT INTO `Services` (`Service_ID`, `Service_Details`) VALUES (457, 'dog license');
INSERT INTO `Services` (`Service_ID`, `Service_Details`) VALUES (575, 'building permit');
INSERT INTO `Services` (`Service_ID`, `Service_Details`) VALUES (606, 'liquor license');
INSERT INTO `Services` (`Service_ID`, `Service_Details`) VALUES (620, 'library card');
INSERT INTO `Services` (`Service_ID`, `Service_Details`) VALUES (828, 'working permit');

CREATE TABLE Customers_and_Services (
Customers_and_Services_ID INTEGER NOT NULL,
Customer_ID INTEGER,
Service_ID INTEGER,
Customers_and_Services_Details CHAR(15) NOT NULL,
PRIMARY KEY (Customers_and_Services_ID),
FOREIGN KEY (Service_ID) REFERENCES Services (Service_ID),
FOREIGN KEY (Customer_ID) REFERENCES Customers (Customer_ID)
);

INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (123, 12, 313, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (130, 12, 620, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (203, 93, 828, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (228, 286, 430, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (350, 113, 313, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (420, 113, 575, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (428, 103, 575, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (465, 217, 457, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (475, 78, 575, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (606, 256, 828, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (669, 293, 457, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (677, 103, 313, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (680, 113, 430, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (683, 119, 828, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (759, 93, 620, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (766, 103, 620, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (795, 173, 606, 'Satisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (823, 286, 575, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (972, 212, 430, 'Unsatisfied');
INSERT INTO `Customers_and_Services` (`Customers_and_Services_ID`, `Customer_ID`, `Service_ID`, `Customers_and_Services_Details`) VALUES (983, 98, 620, 'Satisfied');


CREATE TABLE Customer_Interactions (
Customer_Interaction_ID INTEGER NOT NULL,
Channel_ID INTEGER,
Customer_ID INTEGER,
Service_ID INTEGER,
Status_Code CHAR(15),
Services_and_Channels_Details VARCHAR(255),
PRIMARY KEY (Customer_Interaction_ID),
FOREIGN KEY (Service_ID) REFERENCES Services (Service_ID),
FOREIGN KEY (Channel_ID) REFERENCES Channels (Channel_ID),
FOREIGN KEY (Customer_ID) REFERENCES Customers (Customer_ID)
);

INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (13, 16, 98, 828, 'Close', 'bad');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (21, 78, 12, 606, 'Close', 'good');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (71, 16, 295, 430, 'Close', 'bad');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (117, 45, 103, 313, 'Open', 'bad');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (169, 65, 119, 828, 'Open', 'good');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (225, 55, 173, 313, 'Close', 'bad');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (237, 55, 103, 313, 'Close', 'bad');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (322, 65, 78, 575, 'Stuck', 'bad');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (336, 78, 286, 457, 'Stuck', 'good');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (514, 55, 113, 313, 'Close', 'good');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (552, 45, 32, 575, 'Open', 'good');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (591, 16, 113, 828, 'Close', 'good');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (607, 16, 286, 430, 'Stuck', 'bad');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (749, 65, 103, 313, 'Open', 'good');
INSERT INTO `Customer_Interactions` (`Customer_Interaction_ID`, `Channel_ID`, `Customer_ID`, `Service_ID`, `Status_Code`, `Services_and_Channels_Details`) VALUES (871, 78, 293, 620, 'Stuck', 'bad');


CREATE TABLE Integration_Platform (
Integration_Platform_ID INTEGER NOT NULL,
Customer_Interaction_ID INTEGER NOT NULL,
Integration_Platform_Details VARCHAR(255) NOT NULL,
PRIMARY KEY (Integration_Platform_ID),
FOREIGN KEY (Customer_Interaction_ID) REFERENCES Customer_Interactions (Customer_Interaction_ID)
);
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (299, 225, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (447, 117, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (519, 607, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (536, 322, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (599, 322, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (605, 322, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (626, 117, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (677, 117, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (678, 552, 'Fail');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (747, 322, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (751, 749, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (761, 607, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (784, 607, 'Success');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (812, 322, 'Fail');
INSERT INTO `Integration_Platform` (`Integration_Platform_ID`, `Customer_Interaction_ID`, `Integration_Platform_Details`) VALUES (833, 169, 'Fail');


CREATE TABLE Analytical_Layer (
Analytical_ID INTEGER NOT NULL,
Customers_and_Services_ID VARCHAR(40) NOT NULL,
Pattern_Recognition VARCHAR(255) NOT NULL,
Analytical_Layer_Type_Code CHAR(15),
PRIMARY KEY (Analytical_ID),
FOREIGN KEY (Customers_and_Services_ID) REFERENCES Customers_and_Services (Customers_and_Services_ID)
);
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (11, '123', 'Normal', 'Bottom');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (12, '203', 'Normal', 'Bottom');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (17, '677', 'Normal', 'Middle');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (32, '677', 'Normal', 'Middle');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (36, '123', 'Normal', 'Middle');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (39, '766', 'Normal', 'Top');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (41, '606', 'Normal', 'Top');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (48, '475', 'Normal', 'Top');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (58, '123', 'Special', 'Top');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (60, '228', 'Normal', 'Top');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (66, '823', 'Normal', 'Bottom');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (68, '680', 'Normal', 'Bottom');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (72, '465', 'Special', 'Bottom');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (77, '123', 'Special', 'Bottom');
INSERT INTO `Analytical_Layer` (`Analytical_ID`, `Customers_and_Services_ID`, `Pattern_Recognition`, `Analytical_Layer_Type_Code`) VALUES (82, '420', 'Special', 'Bottom');
