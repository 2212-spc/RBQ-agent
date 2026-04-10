PRAGMA foreign_keys = ON;

CREATE TABLE "customer" (
"Customer_ID" int,
"Name" text,
"Nationality" text,
"Card_Credit" real,
"Level_of_Membership" int,
PRIMARY KEY ("Customer_ID")
);

CREATE TABLE "branch" (
"Branch_ID" int,
"Manager" text,
"Years_opened" int,
"Location_of_office" text,
PRIMARY KEY ("Branch_ID")
);

INSERT INTO  "customer" VALUES (1,"Arthur Morris","Australia","87.00","3");
INSERT INTO  "customer" VALUES (2,"Denis Compton","England","62.44","2");
INSERT INTO  "customer" VALUES (3,"Donald Bradman","Australia","72.57","2");
INSERT INTO  "customer" VALUES (4,"Cyril Washbrook","England","50.85","1");
INSERT INTO  "customer" VALUES (5,"Len Hutton","England","42.75","0");
INSERT INTO  "customer" VALUES (6,"Sid Barnes","Australia","82.25","1");
INSERT INTO  "customer" VALUES (7,"Bill Edrich","England","31.90","1");
INSERT INTO  "customer" VALUES (8,"Lindsay Hassett","Australia","44.28","1");

INSERT INTO  "branch" VALUES (1,"Ashby Lazale",5,"Hartford");
INSERT INTO  "branch" VALUES (2,"Breton Robert",4,"Waterbury");
INSERT INTO  "branch" VALUES (3,"Campbell Jessie",6,"Hartford");
INSERT INTO  "branch" VALUES (4,"Cobb Sedrick",2,"Waterbury");
INSERT INTO  "branch" VALUES (5,"Hayes Steven",3,"Cheshire");
INSERT INTO  "branch" VALUES (6,"Komisarjevsky Joshua",2,"Cheshire");
INSERT INTO  "branch" VALUES (7,"Peeler Russell",6,"Bridgeport");
INSERT INTO  "branch" VALUES (8,"Reynolds Richard",8,"Waterbury");
INSERT INTO  "branch" VALUES (9,"Rizzo Todd",4,"Waterbury");
INSERT INTO  "branch" VALUES (10,"Webb Daniel",2,"Hartford");

CREATE TABLE "customer_order" (
"Customer_ID" int,
"Branch_ID" int,
"Dish_Name" text,
"Quantity" int,
PRIMARY KEY ("Customer_ID","Branch_ID","Dish_Name"),
FOREIGN KEY ("Customer_ID") REFERENCES `customer`("Customer_ID"),
FOREIGN KEY ("Branch_ID") REFERENCES `branch`("Branch_ID")
);

INSERT INTO  "customer_order" VALUES (2,10,"Ma Po Tofu",1);
INSERT INTO  "customer_order" VALUES (2,9,"Kung Pao Chicken",2);
INSERT INTO  "customer_order" VALUES (3,10,"Peking Roasted Duck",1);
INSERT INTO  "customer_order" VALUES (4,6,"Chow Mein",2);
INSERT INTO  "customer_order" VALUES (5,6,"Chow Mein",1);
INSERT INTO  "customer_order" VALUES (1,10,"Spring Rolls",4);






