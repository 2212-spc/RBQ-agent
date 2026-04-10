PRAGMA foreign_keys = ON;
CREATE TABLE `Products` (
`product_id` INTEGER PRIMARY KEY ,
`parent_product_id` INTEGER,
`product_name` VARCHAR(80),
`product_price` DECIMAL(19,4) DEFAULT 0,
`product_color` VARCHAR(50),
`product_size` VARCHAR(50),
`product_description` VARCHAR(255)
);

INSERT INTO Products (`product_id`, `parent_product_id`, `product_name`, `product_price`, `product_color`, `product_size`, `product_description`) VALUES (1, 8, 'Dell monitor', '795.6200', 'Red', 'Medium', 'Latest model!');
INSERT INTO Products (`product_id`, `parent_product_id`, `product_name`, `product_price`, `product_color`, `product_size`, `product_description`) VALUES (2, 3, 'Dell keyboard', '104.0000', 'Yellow', 'Medium', 'Keyboard for games!');
INSERT INTO Products (`product_id`, `parent_product_id`, `product_name`, `product_price`, `product_color`, `product_size`, `product_description`) VALUES (3, 1, 'iPhone6s', '560.9300', 'Red', 'Small', 'Second hand!');
INSERT INTO Products (`product_id`, `parent_product_id`, `product_name`, `product_price`, `product_color`, `product_size`, `product_description`) VALUES (4, 6, 'iWatch', '369.1100', 'Red', 'Medium', 'Designed for sports!');
INSERT INTO Products (`product_id`, `parent_product_id`, `product_name`, `product_price`, `product_color`, `product_size`, `product_description`) VALUES (5, 2, 'Lenovo keyboard', '382.6700', 'Yellow', 'Medium', 'Work smartly!');


CREATE TABLE `Customers` (
`customer_id` INTEGER PRIMARY KEY,
`gender_code` VARCHAR(1) NOT NULL,
`customer_first_name` VARCHAR(50),
`customer_middle_initial` VARCHAR(1),
`customer_last_name` VARCHAR(50),
`email_address` VARCHAR(255),
`login_name` VARCHAR(80),
`login_password` VARCHAR(20),
`phone_number` VARCHAR(255),
`address_line_1` VARCHAR(255),
`town_city` VARCHAR(50),
`county` VARCHAR(50),
`country` VARCHAR(50)
);
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (1, 'Female', 'Carmen', 'K', 'Treutel', 'pgulgowski@example.com', 'murphy07', '58952d0e0d28de32db3b', '(253)336-6277', '646 Herzog Key Suite 702',  'Port Madonnahaven', 'Israel', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (2, 'Male', 'Jace', 'P', 'Mraz', 'zwisozk@example.org', 'desmond.steuber', '7ba2e47aa0904d9fbdbf', '628-468-4228x5917', '67899 Cassin Hollow Suite 071',  'Port Korychester', 'Palau', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (3, 'Male', 'Vickie', 'B', 'Bergnaum', 'herzog.imogene@example.org', 'kihn.alfonso', '83a1afbe21f5ca4cd2d5', '633-223-0975', '395 Christophe Trail',  'Lornaland', 'Moldova', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (4, 'Male', 'Laurianne', 'C', 'Pfeffer', 'columbus.hackett@example.net', 'alena46', '877cbaac266ddb0a513f', '(874)589-9823x696', '14173 Alize Summit',  'Jennyferchester', 'Saint Vincent and the Grenadines', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (5, 'Female', 'Verner', 'V', 'Schulist', 'juliet11@example.net', 'nanderson', 'c3cf21ffb950845c7d39', '(067)124-1804', '69426 Lewis Estates Suite 438',  'Greenfelderberg', 'South Georgia and the South Sandwich Islands', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (6, 'Female', 'Zetta', 'S', 'Streich', 'melody.schuppe@example.org', 'rau.felipe', '52a6ca3fc466757bd7da', '+50(2)2537278491', '4672 Dwight Valleys Apt. 607',  'East Fritz', 'Afghanistan', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (7, 'Male', 'Jailyn', 'C', 'Murray', 'nmarquardt@example.org', 'vwehner', '372350093217369391dd', '+12(1)5491495825', '0933 Mozelle Junctions Suite 416',  'Cliftonberg', 'Reunion', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (8, 'Male', 'Rozella', 'S', 'Crooks', 'gilbert21@example.com', 'jcremin', 'cdda0eefb860f58bd638', '648.826.7415', '0629 Clotilde Mission',  'Ledaville', 'Bangladesh', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (9, 'Female', 'David', 'T', 'West', 'qkoepp@example.org', 'shanie45', 'b4380163b21bf36d5326', '1-852-557-5246x36659', '76015 Zelma Glen Apt. 194',  'Lake Claudiefort', 'Maldives', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (10, 'Unknown', 'America', 'N', 'Nitzsche', 'gino.cruickshank@example.org', 'zsawayn', '9df44b9e0843940e1e87', '(352)290-2941x800', '983 Jamil Way Apt. 732',  'Braunland', 'Swaziland', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (11, 'Male', 'Sincere', 'B', 'Jast', 'fullrich@example.net', 'hosea87', '6b569c0e6af548ff53f9', '342-363-4102x1883', '56465 Raymond Cliffs',  'North Kristybury', 'Iceland', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (12, 'Female', 'Marlen', 'W', 'Anderson', 'emmie.senger@example.net', 'hosea69', '319dd6a930c2657792a4', '+15(7)5437690330', '22704 Thompson Flat',  'West Polly', 'Martinique', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (13, 'Male', 'Jamel', 'E', 'Koelpin', 'bins.nona@example.net', 'stehr.guido', '12acbe4c1c69bbe2feb3', '134-262-9679x29311', '275 Blick Squares',  'Lake Zechariahton', 'Niue', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (14, 'Female', 'Angeline', 'H', 'Huel', 'veum.jalon@example.org', 'parker.providenci', 'd1440743ea0d14fe05cd', '190.171.0323x6749', '03217 Cummings Causeway',  'East Laura', 'Colombia', 'USA');
INSERT INTO Customers (`customer_id`, `gender_code`, `customer_first_name`, `customer_middle_initial`, `customer_last_name`, `email_address`, `login_name`, `login_password`, `phone_number`, `address_line_1`,  `town_city`, `county`, `country`) VALUES (15, 'Male', 'Carmine', 'A', 'Steuber', 'jwatsica@example.net', 'jewell13', '941ccba5e40de7db4ac5', '1-004-853-7921x099', '9318 Hyatt Flats Apt. 999',  'Oletaside', 'Dominican Republic', 'USA');


CREATE TABLE `Customer_Payment_Methods` (
`customer_id` INTEGER NOT NULL,
`payment_method_code` VARCHAR(10) NOT NULL,
FOREIGN KEY (`customer_id` ) REFERENCES `Customers`(`customer_id` )
);
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (15, 'Direct Debit');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (1, 'Direct Debit');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (10, 'Direct Debit');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (13, 'Credit Card');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (9, 'Credit Card');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (8, 'Credit Card');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (13, 'Cheque');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (15, 'Direct Debit');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (4, 'Credit Card');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (7, 'Credit Card');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (6, 'Credit Card');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (14, 'Cheque');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (3, 'Credit Card');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (2, 'Credit Card');
INSERT INTO Customer_Payment_Methods (`customer_id`, `payment_method_code`) VALUES (14, 'Direct Debit');


CREATE TABLE `Invoices` (
`invoice_number` INTEGER PRIMARY KEY,
`invoice_status_code` VARCHAR(10) NOT NULL,
`invoice_date` DATETIME
);
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (1, 'Paid', '2018-03-09 07:16:07');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (2, 'Issued', '2018-01-28 20:08:22');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (3, 'Paid', '2018-02-13 02:16:55');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (4, 'Issued', '2018-03-11 02:04:42');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (5, 'Paid', '2018-03-14 11:58:55');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (6, 'Paid', '2018-02-19 22:12:45');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (7, 'Paid', '2018-02-14 02:48:48');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (8, 'Paid', '2018-03-20 00:29:12');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (9, 'Issued', '2018-02-17 13:52:46');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (10, 'Issued', '2018-02-17 11:18:32');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (11, 'Issued', '2018-03-04 18:54:34');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (12, 'Paid', '2018-03-05 20:09:18');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (13, 'Issued', '2018-01-26 02:23:32');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (14, 'Paid', '2018-03-23 17:12:08');
INSERT INTO Invoices (`invoice_number`, `invoice_status_code`, `invoice_date`) VALUES (15, 'Issued', '2018-02-03 05:46:16');


CREATE TABLE `Orders` (
`order_id` INTEGER PRIMARY KEY,
`customer_id` INTEGER NOT NULL,
`order_status_code` VARCHAR(10) NOT NULL,
`date_order_placed` DATETIME NOT NULL,
FOREIGN KEY (`customer_id` ) REFERENCES `Customers`(`customer_id` )
);
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (1, 5, 'Cancelled', '2017-09-17 16:13:07');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (2, 13, 'Part Completed', '2017-10-14 12:05:48');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (3, 13, 'Cancelled', '2017-09-10 08:27:04');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (4, 11, 'Delivered', '2018-03-19 21:48:59');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (5, 4, 'Delivered', '2017-09-17 07:48:34');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (6, 8, 'Delivered', '2018-03-07 15:34:19');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (7, 4, 'Part Completed', '2017-12-02 13:40:02');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (8, 15, 'Part Completed', '2018-03-01 04:18:28');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (9, 1, 'Part Completed', '2018-03-01 05:25:55');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (10, 15, 'Part Completed', '2017-09-25 14:30:23');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (11, 2, 'Cancelled', '2017-05-27 10:55:13');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (12, 10, 'Cancelled', '2017-11-06 00:37:20');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (13, 6, 'Part Completed', '2017-09-26 06:53:48');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (14, 6, 'Delivered', '2017-05-02 00:04:13');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (15, 1, 'Cancelled', '2017-11-23 04:27:11');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (16, 10, 'Cancelled', '2017-07-19 12:45:12');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (17, 6, 'Delivered', '2017-10-27 11:27:07');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (18, 3, 'Cancelled', '2017-05-15 15:13:44');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (19, 13, 'Part Completed', '2017-12-10 23:45:42');
INSERT INTO Orders (`order_id`, `customer_id`, `order_status_code`, `date_order_placed`) VALUES (20, 10, 'Cancelled', '2017-09-20 22:18:50');



CREATE TABLE `Order_Items` (
`order_item_id` INTEGER PRIMARY KEY ,
`product_id` INTEGER NOT NULL,
`order_id` INTEGER NOT NULL,
`order_item_status_code` VARCHAR(10) NOT NULL,
FOREIGN KEY (`product_id` ) REFERENCES `Products`(`product_id` ),
FOREIGN KEY (`order_id` ) REFERENCES `Orders`(`order_id` )
);

INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (1, 4, 8, 'Delivered');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (2, 3, 4, 'Out of Stock');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (3, 2, 7, 'Delivered');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (4, 1, 10, 'Out of Stock');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (5, 1, 3, 'Delivered');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (6, 1, 18, 'Delivered');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (7, 5, 3, 'Delivered');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (8, 4, 19, 'Out of Stock');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (9, 5, 18, 'Out of Stock');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (10, 3, 6, 'Delivered');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (11, 3, 1, 'Out of Stock');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (12, 5, 10, 'Out of Stock');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (13, 4, 17, 'Delivered');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (14, 1, 19, 'Out of Stock');
INSERT INTO Order_Items (`order_item_id`, `product_id`, `order_id`, `order_item_status_code`) VALUES (15, 3, 20, 'Out of Stock');


CREATE TABLE `Shipments` (
`shipment_id` INTEGER PRIMARY KEY,
`order_id` INTEGER NOT NULL,
`invoice_number` INTEGER NOT NULL,
`shipment_tracking_number` VARCHAR(80),
`shipment_date` DATETIME,
FOREIGN KEY (`invoice_number` ) REFERENCES `Invoices`(`invoice_number` ),
FOREIGN KEY (`order_id` ) REFERENCES `Orders`(`order_id` )
);
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (1, 7, 5, '6900', '2018-02-28 00:04:11');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (2, 6, 2, '3499', '2018-03-07 01:57:14');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (3, 9, 4, '5617', '2018-03-18 22:23:19');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (4, 8, 14, '6074', '2018-03-11 23:48:37');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (5, 12, 9, '3848', '2018-02-25 21:42:52');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (6, 15, 15, '3335', '2018-03-15 01:10:18');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (7, 14, 3, '8731', '2018-03-14 16:21:03');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (8, 12, 5, '6804', '2018-03-12 01:44:44');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (9, 18, 7, '4377', '2018-03-20 01:23:34');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (10, 4, 13, '8149', '2018-03-16 03:30:05');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (11, 6, 2, '9190', '2018-02-25 19:24:52');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (12, 17, 13, '9206', '2018-03-20 21:01:04');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (13, 7, 9, '4276', '2018-03-25 15:37:44');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (14, 5, 11, '9195', '2018-03-10 22:34:34');
INSERT INTO Shipments (`shipment_id`, `order_id`, `invoice_number`, `shipment_tracking_number`, `shipment_date`) VALUES (15, 6, 11, '5506', '2018-03-09 07:24:28');

CREATE TABLE `Shipment_Items` (
`shipment_id` INTEGER NOT NULL,
`order_item_id` INTEGER NOT NULL,
PRIMARY KEY (`shipment_id`,`order_item_id`),
FOREIGN KEY (`shipment_id` ) REFERENCES `Shipments`(`shipment_id` ),
FOREIGN KEY (`order_item_id` ) REFERENCES `Order_Items`(`order_item_id` )
);
INSERT INTO Shipment_Items (`shipment_id`, `order_item_id`) VALUES (4, 4);
INSERT INTO Shipment_Items (`shipment_id`, `order_item_id`) VALUES (7, 14);
INSERT INTO Shipment_Items (`shipment_id`, `order_item_id`) VALUES (15, 9);
INSERT INTO Shipment_Items (`shipment_id`, `order_item_id`) VALUES (8, 14);
INSERT INTO Shipment_Items (`shipment_id`, `order_item_id`) VALUES (9, 15);
INSERT INTO Shipment_Items (`shipment_id`, `order_item_id`) VALUES (6, 14);
