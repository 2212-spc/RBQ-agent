PRAGMA foreign_keys = ON;

CREATE TABLE "Customers" (
"id" int,
"name" text,
"age" int,
"membership_credit" int,
PRIMARY KEY ("id")
);
INSERT INTO  "Customers" VALUES (1, "Griffiths",26, 100);
INSERT INTO  "Customers" VALUES (2, "Silluzio",34, 1200);
INSERT INTO  "Customers" VALUES (3, "Woodman",35, 2000);
INSERT INTO  "Customers" VALUES (4, "Poulter", 63, 43500);
INSERT INTO  "Customers" VALUES (5, "Smith", 45, 5399);


CREATE TABLE "Discount" (
"id" int,
"name" text,
"membership_credit" int,
PRIMARY KEY ("id")
);
INSERT INTO  "Discount" VALUES (1, "no discount", 0);
INSERT INTO  "Discount" VALUES (2, "20% off", 1000);
INSERT INTO  "Discount" VALUES (3, "40% off for over $6000", 2000);
INSERT INTO  "Discount" VALUES (4, "50% off", 4000);
INSERT INTO  "Discount" VALUES (5, "70% off", 400000);


CREATE TABLE "Vehicles" (
"id" int,
"name" text,
"Model_year" int,
"Type_of_powertrain" text,
"Combined_fuel_economy_rate" int,
"City_fuel_economy_rate" int,
"Highway_fuel_economy_rate" int,
"Cost_per_25_miles" real,
"Annual_fuel_cost" real,
"Notes" text,
PRIMARY KEY ("id")
);



INSERT INTO  "Vehicles" VALUES (1, "Chevrolet Spark EV","2014","Electric","119","128","109","0.87","500","See (1)");
INSERT INTO  "Vehicles" VALUES (2, "Honda Fit EV","2013","hybrid","118","132","105","0.87","500","See (1)");
INSERT INTO  "Vehicles" VALUES (3, "Fiat 500e","2013","Electric","116","122","108","0.87","500","See (1)");
INSERT INTO  "Vehicles" VALUES (4, "Nissan Leaf","2013","Electric","115","129","102","0.87","500","See (1)");
INSERT INTO  "Vehicles" VALUES (5, "Mitsubishi i","2012","hybrid","112","126","99","0.90","550","best selling of the year");
INSERT INTO  "Vehicles" VALUES (6, "Ford Focus Electric","2012","electric","105","110","99","0.96","600","See (2)");
INSERT INTO  "Vehicles" VALUES (7, "BMW ActiveE","2011","Electric","102","107","96","0.99","600","See (1)");


CREATE TABLE "Renting_history" (
"id" int,
"customer_id" int,
"discount_id" int,
"vehicles_id" int,
"total_hours" int,
PRIMARY KEY ("id"),
FOREIGN KEY ("customer_id") REFERENCES "Customers"("id"),
FOREIGN KEY ("vehicles_id") REFERENCES "Vehicles"("id"),
FOREIGN KEY ("discount_id") REFERENCES "Discount"("id")
);



INSERT INTO  "Renting_history" VALUES (1,1,1,2,1);
INSERT INTO  "Renting_history" VALUES (2,2,2,5,10);
INSERT INTO  "Renting_history" VALUES (3,3,3,7,24);
INSERT INTO  "Renting_history" VALUES (4,4,4,3,24);
INSERT INTO  "Renting_history" VALUES (5,1,1,5,36);
INSERT INTO  "Renting_history" VALUES (6,2,2,1,24);
INSERT INTO  "Renting_history" VALUES (7,5,4,4,72);


