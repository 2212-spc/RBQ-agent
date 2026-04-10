
PRAGMA foreign_keys = ON;

CREATE TABLE Students (
Student_ID INTEGER NOT NULL,
First_Name VARCHAR(255),
Middle_Name VARCHAR(255),
Last_Name VARCHAR(255),
Gender_MFU CHAR(1),
Student_Address VARCHAR(255),
Email_Adress VARCHAR(255),
Cell_Mobile_Phone VARCHAR(255),
Home_Phone VARCHAR(255),
PRIMARY KEY (Student_ID)
);
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (5, 'Wilbert', 'Mia', 'Conroy', 'F', '2908 Breana Streets Suite 638', 'rjast@example.com', '620.962.4384x340', '017-084-5752x96504');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (6, 'Abdul', 'Era', 'Renner', 'M', '009 Vandervort Ferry', 'green.jesus@example.net', '03437137203', '(054)515-8842x4046');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (11, 'Ari', 'Jacinthe', 'Kessler', 'M', '053 Candido Port Suite 568', 'oschamberger@example.net', '207-458-7971', '220.735.2352x52387');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (15, 'Cassidy', 'Karson', 'Gerhold', 'U', '25250 Alexander Spring Apt. 106', 'alvera52@example.com', '1-077-467-7564', '715.670.8396x276');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (17, 'Alfreda', 'Queen', 'Schuster', 'M', '1110 Kaylee Greens Apt. 491', 'bogan.barton@example.net', '038-482-3730x66922', '1-400-038-3818x39652');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (22, 'Betsy', 'Larue', 'Orn', 'M', '71938 Dickinson Summit Suite 683', 'jana90@example.com', '1-922-743-4349', '377-581-9036');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (24, 'Yadira', 'Matteo', 'Rohan', 'U', '3679 Huels Ranch', 'gusikowski.retta@example.net', '084-076-8037x1728', '743.322.8573x380');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (35, 'Deven', 'Gino', 'Deckow', 'U', '49860 Cesar Pine', 'ezekiel53@example.com', '+08(7)2834974200', '+23(7)3611361591');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (37, 'Haylie', 'Rupert', 'Wiegand', 'U', '988 Hettinger Pine Apt. 005', 'kschroeder@example.org', '1-185-860-6666x236', '048.938.2113x0806');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (38, 'Jeromy', 'Rebekah', 'Torp', 'F', '59773 Misty Loop', 'dhermiston@example.net', '1-197-438-2369', '015.452.3914');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (40, 'Cloyd', 'Rolando', 'Kertzmann', 'F', '437 Ambrose Flats Apt. 321', 'albin40@example.org', '(304)107-3579', '1-838-315-5041x9245');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (41, 'Adam', 'Caden', 'Roob', 'M', '1551 Petra Terrace', 'kane.o''conner@example.net', '1-309-808-1855', '(868)144-5163');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (45, 'Flavio', 'Arnaldo', 'Conroy', 'F', '06494 Felipa Ranch', 'raleigh28@example.net', '(846)394-0048x51720', '983-853-1844x3209');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (52, 'Jaylen', 'Nicola', 'Cummerata', 'U', '713 Loyal Road', 'sfahey@example.org', '(275)623-3304', '383-313-3627x634');
INSERT INTO `Students` (`Student_ID`, `First_Name`, `Middle_Name`, `Last_Name`, `Gender_MFU`, `Student_Address`, `Email_Adress`, `Cell_Mobile_Phone`, `Home_Phone`) VALUES (93, 'Lindsey', 'Therese', 'Lehner', 'U', '6279 Vicky Ridges', 'hahn.elza@example.com', '(651)517-2936x38712', '(467)314-3743');


CREATE TABLE Questions (
Question_ID INTEGER NOT NULL,
Type_of_Question_Code VARCHAR(15) NOT NULL,
Question_Text VARCHAR(255),
PRIMARY KEY (Question_ID)
);
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (285, 'Single Choice', 'When is middle age period');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (321, 'Multiple Choice', 'Who are from Renaissance age');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (585, 'Multiple Choice', 'Which are the works from Picasso');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (603, 'Multiple Choice', 'Which are the works from Van Gogh');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (613, 'Multiple Choice', 'Which are answers for the blanks in the passage');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (655, 'Multiple Choice', 'Which are answers for the blanks in the passage');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (682, 'Multiple Choice', 'Which are answers for the blanks in the passage?');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (710, 'Free Text', 'Is it true that queue is FIFO');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (721, 'Multiple Choice', 'Choose which structures are linear');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (839, 'Single Choice', 'Choose the definition of a foreign key');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (856, 'Single Choice', 'Choose the definition of SQL');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (863, 'Free Text', 'What is a join');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (948, 'Multiple Choice', 'Choose the definition of a primary key');
INSERT INTO `Questions` (`Question_ID`, `Type_of_Question_Code`, `Question_Text`) VALUES (996, 'Multiple Choice', 'What is a table');


CREATE TABLE Exams (
Exam_ID INTEGER NOT NULL,
Subject_Code CHAR(15) NOT NULL,
Exam_Date DATETIME,
Exam_Name VARCHAR(255),
PRIMARY KEY (Exam_ID)
);
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (1, 'Art History', '2016-01-28 02:03:40', '2016 Spring AH');
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (2, 'Art History', '2017-11-17 09:21:31', '2017 Fall AH');
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (3, 'English', '2016-12-19 02:40:33', '2016 Winter ENG');
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (4, 'Database', '2016-06-17 07:20:06', '2016 Summer DB');
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (5, 'Database', '2017-02-26 11:19:52', '2017 Spring DB');
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (6, 'Art History', '2016-08-10 21:39:15', '2016 Summer AH');
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (7, 'Database', '2017-08-25 07:48:19', '2017 Summer DB');
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (8, 'Database', '2015-08-21 22:15:06', '2015 Summer DB');
INSERT INTO `Exams` (`Exam_ID`, `Subject_Code`, `Exam_Date`, `Exam_Name`) VALUES (9, 'Data Structure', '2017-08-04 05:43:39', '2017 Summer DS');


CREATE TABLE Questions_in_Exams (
Exam_ID INTEGER NOT NULL,
Question_ID INTEGER NOT NULL,
PRIMARY KEY (Exam_ID, Question_ID),
FOREIGN KEY (Question_ID) REFERENCES Questions (Question_ID),
FOREIGN KEY (Exam_ID) REFERENCES Exams (Exam_ID)
);

INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (1, 321);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (1, 285);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (2, 585);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (2, 603);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (3, 613);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (3, 682);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (3, 655);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (9, 710);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (9, 721);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (8, 839);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (8, 856);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (7, 863);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (4, 948);
INSERT INTO `Questions_in_Exams` (`Exam_ID`, `Question_ID`) VALUES (5, 996);

CREATE TABLE Valid_Answers (
Valid_Answer_ID INTEGER NOT NULL,
Question_ID INTEGER NOT NULL,
Valid_Answer_Text VARCHAR(255),
PRIMARY KEY (Valid_Answer_ID),
FOREIGN KEY (Question_ID) REFERENCES Questions (Question_ID)
);
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (1, 321, 'ABC');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (2, 721, 'ABC');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (3, 996, 'C');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (4, 839, 'C');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (5, 285, 'C');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (6, 613, 'ABC');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (7, 603, 'ABC');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (8, 721, 'ABC');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (9, 285, 'C');
INSERT INTO `Valid_Answers` (`Valid_Answer_ID`, `Question_ID`, `Valid_Answer_Text`) VALUES (10, 655, 'ABC');

CREATE TABLE Student_Answers (
Student_Answer_ID INTEGER NOT NULL,
Exam_ID INTEGER NOT NULL,
Question_ID INTEGER NOT NULL,
Student_ID INTEGER NOT NULL,
Date_of_Answer DATETIME,
Comments VARCHAR(255),
Satisfactory_YN VARCHAR(1),
Student_Answer_Text VARCHAR(255),
PRIMARY KEY (Student_Answer_ID),
FOREIGN KEY (Student_ID) REFERENCES Students (Student_ID),
FOREIGN KEY (Exam_ID, Question_ID) REFERENCES Questions_in_Exams (Exam_ID,Question_ID)
);
CREATE TABLE Student_Assessments (
Student_Answer_ID VARCHAR(100) NOT NULL,
Valid_Answer_ID INTEGER NOT NULL,
Student_Answer_Text VARCHAR(255),
Satisfactory_YN CHAR(1),
Assessment VARCHAR(40),
PRIMARY KEY (Student_Answer_ID),
FOREIGN KEY (Valid_Answer_ID) REFERENCES Valid_Answers (Valid_Answer_ID)
);
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (127, 1,321, 52, '2017-08-13 06:03:03', 'Normal', '0', 'D');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (149, 1, 285, 22, '2017-07-27 06:34:17', 'Normal', '1', 'ABC');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (169, 2, 585, 40, '2017-07-30 12:07:59', 'Normal', '1', 'ABC');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (284, 2, 603, 35, '2018-02-21 09:14:48', 'Normal', '1', 'ABC');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (374, 3, 655, 6, '2017-12-04 10:10:48', 'Normal', '1', 'ABC');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (397, 3, 613, 52, '2017-12-21 16:40:17', 'Normal', '0', 'BCD');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (455, 3, 682, 15, '2017-05-13 07:29:20', 'Normal', '1', 'ABC');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (460, 9, 721, 93, '2018-01-10 21:22:57', 'Normal', '0', 'AC');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (544, 8, 839, 6, '2017-11-04 00:23:29', 'Normal', '1', 'C');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (564, 8, 856, 22, '2017-07-27 18:22:08', 'Normal', '1', 'C');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (577, 5, 996, 38, '2017-10-11 18:29:01', 'Absent', '0', 'Student absent');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (701, 7, 863, 37, '2017-05-20 03:44:40', 'Absent', '0', 'Student absent');
INSERT INTO `Student_Answers` (`Student_Answer_ID`, `Exam_ID`, `Question_ID`, `Student_ID`, `Date_of_Answer`, `Comments`, `Satisfactory_YN`, `Student_Answer_Text`) VALUES (778, 4, 948, 38, '2017-07-08 17:36:15', 'Absent', '1', 'ABC');

INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('162', 3, 'B', '0', 'Very Good');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('172', 4, 'B', '0', 'Excellent');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('2', 3, 'A', '1', 'Very Good');

INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('307', 2, 'True', '0', 'Very Good');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('340', 3, 'False', '1', 'OK');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('421', 1, 'B', '1', 'Excellent');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('438', 2, 'True', '0', 'Excellent');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('518', 3, 'B', '0', 'OK');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('536', 4, 'A', '1', 'Excellent');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('540', 5, 'True', '1', 'OK');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('565', 6, 'True', '1', 'Excellent');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('9', 7, 'A', '0', 'OK');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('956', 10, 'A', '1', 'Excellent');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('961', 10, 'False', '0', 'OK');
INSERT INTO `Student_Assessments` (`Student_Answer_ID`, `Valid_Answer_ID`, `Student_Answer_Text`, `Satisfactory_YN`, `Assessment`) VALUES ('980', 10, 'A', '1', 'Excellent');
