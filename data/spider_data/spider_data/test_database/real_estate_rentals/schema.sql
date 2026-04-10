PRAGMA foreign_keys = ON;

CREATE TABLE `Ref_Age_Categories` (
`age_category_code` VARCHAR(15) PRIMARY KEY,
`age_category_description` VARCHAR(80)
);
CREATE TABLE `Ref_Property_Types` (
`property_type_code` VARCHAR(15) PRIMARY KEY,
`property_type_description` VARCHAR(80)
);
CREATE TABLE `Ref_Room_Types` (
`room_type_code` VARCHAR(15) PRIMARY KEY,
`room_type_description` VARCHAR(80)
);
CREATE TABLE `Ref_User_Categories` (
`user_category_code` VARCHAR(15) PRIMARY KEY,
`user_category_description` VARCHAR(80)
);
INSERT INTO Ref_Age_Categories (`age_category_code`, `age_category_description`) VALUES ('18-25', '18 - 25 years old.');
INSERT INTO Ref_Age_Categories (`age_category_code`, `age_category_description`) VALUES ('Over 60', 'Over 60 years of age.');
INSERT INTO Ref_Age_Categories (`age_category_code`, `age_category_description`) VALUES ('25-60', '25 - 60 years old.');
INSERT INTO Ref_Property_Types (`property_type_code`, `property_type_description`) VALUES ('7', 'flat');
INSERT INTO Ref_Property_Types (`property_type_code`, `property_type_description`) VALUES ('8', 'house');
INSERT INTO Ref_Property_Types (`property_type_code`, `property_type_description`) VALUES ('2', 'apt');
INSERT INTO Ref_Room_Types (`room_type_code`, `room_type_description`) VALUES ('2', 'living');
INSERT INTO Ref_Room_Types (`room_type_code`, `room_type_description`) VALUES ('8', 'kitchen');
INSERT INTO Ref_Room_Types (`room_type_code`, `room_type_description`) VALUES ('4', 'bath');
INSERT INTO Ref_Room_Types (`room_type_code`, `room_type_description`) VALUES ('3', 'bedroom');
INSERT INTO Ref_User_Categories (`user_category_code`, `user_category_description`) VALUES ('Student', 'Student');
INSERT INTO Ref_User_Categories (`user_category_code`, `user_category_description`) VALUES ('Senior Citizen', 'Senior Citizen');
INSERT INTO Ref_User_Categories (`user_category_code`, `user_category_description`) VALUES ('Single Mother', 'Single Mother');


CREATE TABLE `Addresses` (
`address_id` INTEGER PRIMARY KEY,
`line_1_number_building` VARCHAR(80),
`line_2_number_street` VARCHAR(80),
`line_3_area_locality` VARCHAR(80),
`town_city` VARCHAR(80),
`zip_postcode` VARCHAR(20),
`county_state_province` VARCHAR(80),
`country` VARCHAR(50),
`other_address_details` VARCHAR(255)
);
CREATE TABLE `Features` (
`feature_id` INTEGER PRIMARY KEY,
`feature_name` VARCHAR(80),
`feature_description` VARCHAR(80)
);

INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (1, '6207 Marks Trafficway', 'Apt. 516', NULL, 'Port Miafurt', '349', 'Utah', 'United States Minor Outlying Islands', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (2, '518 Dean Village', 'Apt. 261', NULL, 'New Juliana', '979', 'Maryland', 'South Georgia and the South Sandwich Islands', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (3, '88324 Medhurst Parkway Suite 832', 'Suite 435', NULL, 'Jaquanmouth', '937', 'RhodeIsland', 'Hungary', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (4, '44916 Hand Branch', 'Apt. 237', NULL, 'New Augusta', '385', 'Alaska', 'Jersey', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (5, '929 Hermiston Vista Suite 955', 'Apt. 235', NULL, 'New Zachariahport', '416', 'Louisiana', 'Western Sahara', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (6, '8559 Birdie Mountain', 'Suite 515', NULL, 'East Percivalfurt', '298', 'Maryland', 'Ethiopia', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (7, '0548 Xavier Ridge Apt. 397', 'Apt. 802', NULL, 'South Jakob', '356', 'Oklahoma', 'Christmas Island', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (8, '6355 Maida Shores Suite 839', 'Apt. 058', NULL, 'Lake Ezraborough', '269', 'Nevada', 'Marshall Islands', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (9, '0182 Schuppe Ferry', 'Suite 619', NULL, 'Mckenzieton', '595', 'Illinois', 'Turkey', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (10, '80901 Lakin Point', 'Apt. 948', NULL, 'Adityaport', '684', 'Wyoming', 'Aruba', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (11, '15594 Nicholaus Ports', 'Apt. 284', NULL, 'Port Forest', '697', 'Michigan', 'Djibouti', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (12, '11179 Price Junctions', 'Apt. 295', NULL, 'South Brandtport', '146', 'Colorado', 'Svalbard & Jan Mayen Islands', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (13, '1592 Marielle Throughway', 'Suite 482', NULL, 'Hermistonburgh', '772', 'Illinois', 'Grenada', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (14, '340 Cleta Orchard Apt. 866', 'Apt. 226', NULL, 'South Raymond', '394', 'Missouri', 'Macedonia', NULL);
INSERT INTO Addresses (`address_id`, `line_1_number_building`, `line_2_number_street`, `line_3_area_locality`, `town_city`, `zip_postcode`, `county_state_province`, `country`, `other_address_details`) VALUES (15, '5740 Maxwell Union Suite 546', 'Suite 073', NULL, 'Port Johan', '179', 'Oklahoma', 'Guam', NULL);
INSERT INTO Features (`feature_id`, `feature_name`, `feature_description`) VALUES (1, 'kichen', 'ea');
INSERT INTO Features (`feature_id`, `feature_name`, `feature_description`) VALUES (2, 'rooftop', 'vel');
INSERT INTO Features (`feature_id`, `feature_name`, `feature_description`) VALUES (3, 'garden', 'et');
INSERT INTO Features (`feature_id`, `feature_name`, `feature_description`) VALUES (4, 'swimming pool', 'id');
INSERT INTO Features (`feature_id`, `feature_name`, `feature_description`) VALUES (5, 'high building', 'facere');


CREATE TABLE `Users` (
`user_id` INTEGER PRIMARY KEY,
`age_category_code` VARCHAR(15),
`user_category_code` VARCHAR(15),
`user_address_id` INTEGER NOT NULL,
`is_buyer` VARCHAR(1),
`is_seller` VARCHAR(1),
`login_name` VARCHAR(25),
`password` VARCHAR(8),
`date_registered` DATETIME,
`first_name` VARCHAR(80),
`middle_name` VARCHAR(80),
`last_name` VARCHAR(80),
`other_user_details` VARCHAR(255)
);

INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (1, '18-25', 'Senior Citizen', 5, '1', '', 'dolor', 'a9dc84fe', '1980-12-28 20:26:12', 'Madonna', 'Kristoffer', 'Jaskolski', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (2, '25-60', 'Senior Citizen', 6, '1', '', 'et', '7daed599', '1985-06-02 00:10:47', 'Miguel', 'Dovie', 'Harber', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (3, 'Over 60', 'Senior Citizen', 15, '1', '', 'repellat', '7061d718', '1977-09-28 23:37:31', 'Robbie', 'Angelo', 'Keeling', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (4, '18-25', 'Single Mother', 4, '1', '', 'laboriosam', 'f78651d8', '2016-12-01 10:47:14', 'Phoebe', 'Mike', 'Kohler', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (5, 'Over 60', 'Senior Citizen', 10, '', '1', 'corrupti', '073f78a2', '1975-12-17 05:04:32', 'Brielle', 'Mariane', 'Haley', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (6, '18-25', 'Senior Citizen', 14, '1', '', 'omnis', '6d1ed7a2', '1999-02-25 13:45:33', 'Reggie', 'Eulah', 'Ernser', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (7, '25-60', 'Student', 9, '1', '', 'qui', 'a44394fb', '1988-08-11 19:23:27', 'Brett', 'Jaylon', 'Runte', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (8, 'Over 60', 'Senior Citizen', 9, '', '1', 'ratione', '6af1990c', '2015-07-29 08:52:10', 'Porter', 'Creola', 'Mohr', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (9, 'Over 60', 'Single Mother', 1, '1', '', 'ut', 'b865e655', '1993-10-17 04:08:26', 'Jameson', 'Jaylin', 'Rippin', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (10, '18-25', 'Single Mother', 1, '1', '', 'in', 'bdad75c8', '1980-07-04 17:28:15', 'Dane', 'Casey', 'Fritsch', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (11, 'Over 60', 'Single Mother', 11, '1', '', 'doloremque', '14567850', '1976-05-19 04:53:59', 'Gudrun', 'Brock', 'West', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (12, '18-25', 'Senior Citizen', 5, '', '1', 'harum', '223970d3', '2006-01-19 12:22:54', 'Ruby', 'Trenton', 'Schulist', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (13, '25-60', 'Student', 14, '', '1', 'culpa', 'b264c8b7', '1979-03-14 08:07:49', 'Antonio', 'Kitty', 'Cronin', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (14, 'Over 60', 'Senior Citizen', 10, '1', '', 'consequatur', 'bd0a8b12', '2006-08-20 02:16:04', 'D''angelo', 'Brisa', 'Nienow', NULL);
INSERT INTO Users (`user_id`, `age_category_code`, `user_category_code`, `user_address_id`, `is_buyer`, `is_seller`, `login_name`, `password`, `date_registered`, `first_name`, `middle_name`, `last_name`, `other_user_details`) VALUES (15, '25-60', 'Student', 1, '1', '', 'omnis', '81cce049', '2001-04-26 09:27:50', 'Theresa', 'Thurman', 'Bartell', NULL);


CREATE TABLE `Properties` (
`property_id` INTEGER PRIMARY KEY,
`property_address_id` INTEGER NOT NULL,
`owner_user_id` INTEGER NOT NULL,
`property_type_code` VARCHAR(15) NOT NULL,
`date_on_market` DATETIME,
`date_off_market` DATETIME,
`property_name` VARCHAR(80),
`property_description` VARCHAR(255),
`garage_yn` VARCHAR(1),
`parking_lots` VARCHAR(1),
`room_count` VARCHAR(10),
`vendor_requested_price` DOUBLE NULL,
`price_min` DOUBLE NULL,
`price_max` DOUBLE NULL,
`other_property_details` VARCHAR(255),
FOREIGN KEY (`owner_user_id` ) REFERENCES `Users`(`user_id` ),
FOREIGN KEY (`property_address_id` ) REFERENCES `Addresses`(`address_id` ),
FOREIGN KEY (`property_type_code` ) REFERENCES `Ref_Property_Types`(`property_type_code` )
);

CREATE TABLE `Property_Features` (
`property_id` INTEGER NOT NULL,
`feature_id` INTEGER NOT NULL,
`feature_value` VARCHAR(80),
`property_feature_description` VARCHAR(80),
FOREIGN KEY (`feature_id` ) REFERENCES `Features`(`feature_id` ),
FOREIGN KEY (`property_id` ) REFERENCES `Properties`(`property_id` )
);
CREATE TABLE `Property_Photos` (
`property_id` INTEGER NOT NULL,
`photo_seq` INTEGER NOT NULL,
`photo_title` VARCHAR(30),
`photo_description` VARCHAR(255),
`photo_filename` VARCHAR(255),
FOREIGN KEY (`property_id` ) REFERENCES `Properties`(`property_id` )
);

CREATE TABLE `Rooms` (
`property_id` INTEGER NOT NULL,
`room_number` VARCHAR(10) NOT NULL,
`room_type_code` VARCHAR(15) NOT NULL,
`room_size` VARCHAR(20),
`other_room_details` VARCHAR(255),
FOREIGN KEY (`property_id` ) REFERENCES `Properties`(`property_id` ),
FOREIGN KEY (`room_type_code` ) REFERENCES `Ref_Room_Types`(`room_type_code` )
);
CREATE TABLE `User_Property_History` (
`user_id` INTEGER NOT NULL,
`property_id` INTEGER NOT NULL,
`datestamp` DATETIME NOT NULL,
FOREIGN KEY (`user_id` ) REFERENCES `Users`(`user_id` ),
FOREIGN KEY (`property_id` ) REFERENCES `Properties`(`property_id` )
);
CREATE TABLE `User_Searches` (
`user_id` INTEGER NOT NULL,
`search_seq` INTEGER NOT NULL,
`search_datetime` DATETIME,
`search_string` VARCHAR(80),
FOREIGN KEY (`user_id` ) REFERENCES `Users`(`user_id` )
);




INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (1, 9, 13, '7', '2015-06-16 01:43:42', '1978-11-17 22:49:30', 'garden', 'dolores', '1', '', '7', '2454.682', '20835877.439261', '352563032.06431', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (2, 8, 5, '8', '2014-10-10 10:17:36', '2006-09-25 06:39:14', 'studio', 'quis', '', '1', '8', '409217.49906266', '498.39', '55837.914362', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (3, 7, 10, '2', '2011-12-15 01:52:28', '2017-05-27 20:55:25', 'garden', 'facere', '1', '1', '9', '60571695.39357', '3897.55448', '1887', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (4, 12, 7, '7', '1971-01-17 04:08:35', '1971-08-25 01:13:02', 'studio', 'ut', '', '1', '4', '3.009911', '208147.904976', '227.624634182', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (5, 4, 9, '8', '1996-12-17 20:53:52', '2000-03-16 23:04:27', 'garden', 'perspiciatis', '1', '1', '1', '47605468.125659', '335.875884731', '0', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (6, 14, 6, '7', '1989-04-04 17:34:41', '1981-08-03 12:46:34', 'studio', 'dolorum', '1', '', '1', '46382985.88415', '0.0866', '0', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (7, 2, 4, '8', '2000-09-08 06:54:00', '2002-10-13 04:52:26', 'park', 'earum', '1', '1', '8', '428517.1', '22130.13', '0', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (8, 15, 13, '7', '2010-09-27 19:19:44', '1998-08-19 19:29:50', 'studio', 'ad', '1', '', '3', '3076499.25', '0', '7.4', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (9, 8, 10, '2', '2002-01-06 18:44:23', '1978-09-24 13:42:49', 'park', 'magni', '', '', '7', '19.917482', '407995518.00153', '194724.15425105', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (10, 14, 2, '7', '1996-10-13 18:04:10', '1981-02-04 02:00:30', 'park', 'libero', '', '', '8', '0.15837612', '2855', '2734817.1574795', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (11, 5, 10, '2', '1976-08-01 00:52:48', '1970-11-22 02:09:50', 'house', 'dolorem', '1', '', '9', '294154.455', '18123757.317', '471.9874856', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (12, 9, 3, '7', '1985-09-03 23:35:59', '2011-11-28 01:18:51', 'house', 'eum', '', '1', '7', '551.53493622', '24001489.487911', '1', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (13, 2, 9, '2', '2010-06-02 05:49:21', '1990-01-25 07:42:34', 'garage', 'perspiciatis', '1', '1', '9', '1222.603328', '6628.9', '0', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (14, 13, 6, '7', '2001-04-15 21:14:41', '1981-09-12 05:26:47', 'garage', 'vel', '', '1', '8', '1435608.608', '1.3248', '40172.49', NULL);
INSERT INTO Properties (`property_id`, `property_address_id`, `owner_user_id`, `property_type_code`, `date_on_market`, `date_off_market`, `property_name`, `property_description`, `garage_yn`, `parking_lots`, `room_count`, `vendor_requested_price`, `price_min`, `price_max`, `other_property_details`) VALUES (15, 15, 9, '2', '1992-09-12 03:18:04', '1992-06-20 14:37:39', 'garage', 'expedita', '1', '1', '8', '0', '14323.3095', '94621091.987512', NULL);
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (14, 3, 'temporibus', 'est');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (4, 2, 'et', 'nam');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (4, 2, 'necessitatibus', 'voluptates');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (2, 2, 'quo', 'et');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (8, 3, 'fuga', 'esse');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (1, 4, 'unde', 'ipsam');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (3, 3, 'est', 'ratione');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (12, 2, 'aspernatur', 'explicabo');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (3, 3, 'voluptas', 'omnis');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (3, 4, 'at', 'ut');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (13, 5, 'eligendi', 'quasi');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (9, 2, 'harum', 'vel');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (9, 5, 'asperiores', 'quod');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (5, 1, 'delectus', 'molestiae');
INSERT INTO Property_Features (`property_id`, `feature_id`, `feature_value`, `property_feature_description`) VALUES (13, 5, 'eligendi', 'commodi');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (5, 0, 'front', 'reiciendis', 'repellat');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (15, 61822, 'front', 'aut', 'iste');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (8, 0, 'front', 'officiis', 'id');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (14, 0, 'back', 'in', 'error');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (14, 3961, 'back', 'eum', 'sed');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (9, 2, 'back', 'rerum', 'ea');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (6, 1591, 'kitchen', 'iusto', 'accusantium');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (14, 42490707, 'kitchen', 'commodi', 'sed');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (14, 13182, 'bathroom', 'modi', 'eos');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (9, 98, 'bathroom', 'ut', 'corporis');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (10, 0, 'bedroom', 'accusamus', 'dolor');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (14, 28, 'bedroom', 'ullam', 'quo');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (7, 42, 'bedroom', 'aut', 'sunt');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (12, 66905, 'living room', 'dolor', 'et');
INSERT INTO Property_Photos (`property_id`, `photo_seq`, `photo_title`, `photo_description`, `photo_filename`) VALUES (11, 180487, 'living room', 'omnis', 'et');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (14, '2', '8', 's', 'praesentium');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (1, '1', '2', 's', 'repudiandae');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (15, '7', '2', 'l', 'enim');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (4, '5', '2', 'l', 'nemo');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (1, '8', '4', 's', 'adipisci');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (13, '2', '4', 'm', 'quibusdam');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (6, '4', '2', 'm', 'eum');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (10, '9', '3', 'm', 'maxime');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (6, '5', '4', 's', 'itaque');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (8, '4', '4', 'm', 'qui');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (3, '3', '3', 'm', 'non');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (9, '7', '3', 's', 'impedit');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (5, '6', '4', 'l', 'nesciunt');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (7, '1', '8', 'l', 'ullam');
INSERT INTO Rooms (`property_id`, `room_number`, `room_type_code`, `room_size`, `other_room_details`) VALUES (13, '9', '8', 'let', 'totam');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (11, 2, '2014-07-18 19:21:51');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (2, 7, '1992-07-19 19:34:27');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (8, 7, '2005-11-02 07:47:38');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (4, 9, '1985-12-16 11:41:27');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (15, 13, '2018-02-10 21:19:14');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (7, 15, '2004-02-24 14:27:34');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (7, 8, '2011-10-08 00:04:34');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (8, 3, '2014-10-02 05:34:09');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (12, 12, '1993-08-16 03:26:05');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (2, 4, '2001-09-05 04:01:41');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (12, 1, '1982-10-11 13:46:08');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (13, 15, '1977-03-13 18:50:48');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (4, 2, '2006-10-30 22:13:52');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (5, 3, '1982-08-06 07:39:40');
INSERT INTO User_Property_History (`user_id`, `property_id`, `datestamp`) VALUES (1, 4, '1997-07-08 09:25:24');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (13, 50636, '2014-04-28 20:21:54', 'optio');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (1, 203, '1981-11-21 22:02:12', 'assumenda');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (11, 5054, '1972-04-13 22:48:13', 'consequatur');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (4, 923800, '2007-09-11 14:19:26', 'laudantium');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (5, 82475512, '1981-01-01 16:48:00', 'laboriosam');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (13, 24321735, '1971-04-24 20:18:31', 'repellat');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (15, 85717, '1994-11-07 23:31:00', 'maiores');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (2, 45340, '1989-12-21 19:39:20', 'facilis');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (4, 56003, '2004-04-08 09:29:30', 'inventore');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (2, 778216600, '2015-10-18 18:21:09', 'nesciunt');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (5, 1551910, '2014-08-31 08:26:53', 'aliquam');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (11, 0, '1975-11-17 19:59:16', 'at');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (10, 7, '2000-07-17 14:19:27', 'hic');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (4, 45181074, '1983-05-12 23:48:23', 'est');
INSERT INTO User_Searches (`user_id`, `search_seq`, `search_datetime`, `search_string`) VALUES (3, 327708, '1985-11-06 17:10:05', 'fugiat');
