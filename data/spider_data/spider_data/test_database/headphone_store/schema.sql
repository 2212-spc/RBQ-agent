PRAGMA foreign_keys = ON;

CREATE TABLE "headphone" (
"Headphone_ID" int,
"Model" text,
"Class" text,
"Driver-matched_dB" real,
"Construction" text,
"Earpads" text,
"Price" int,
PRIMARY KEY ("Headphone_ID")
);

CREATE TABLE "store" (
"Store_ID" int,
"Name" text,
"Neighborhood" text,
"Parking" text,
"Date_Opened" text,
PRIMARY KEY ("Store_ID")
);

INSERT INTO  "headphone" VALUES (1,"iGrado","Prestige","0.1","Plastic","Comfort Pads","49");
INSERT INTO  "headphone" VALUES (2,"SR60i","Prestige","0.1","Plastic","Comfort Pads","79");
INSERT INTO  "headphone" VALUES (3,"SR80i","Prestige","0.1","Plastic","Comfort Pads","99");
INSERT INTO  "headphone" VALUES (4,"SR125i","Prestige","0.1","Plastic","Comfort Pads","150");
INSERT INTO  "headphone" VALUES (5,"SR225i","Prestige","0.05","Plastic","Bowls","200");
INSERT INTO  "headphone" VALUES (6,"SR325i","Prestige","0.05","Aluminum alloy/ Plastic inner sleeve","Bowls","295");
INSERT INTO  "headphone" VALUES (7,"RS2i","Reference","0.05","Hand-Crafted Mahogany","Bowls","495");
INSERT INTO  "headphone" VALUES (8,"RS1i","Reference","0.05","Hand-Crafted Mahogany","Bowls","695");
INSERT INTO  "headphone" VALUES (9,"GS1000i","Statement","0.05","Hand-Crafted Mahogany","Circumaural Bowls","995");
INSERT INTO  "headphone" VALUES (10,"PS500","Professional","0.05","Hand-Crafted Mahogany / Aluminum","Bowls","595");
INSERT INTO  "headphone" VALUES (11,"PS1000","Professional","0.05","Hand-Crafted Mahogany / Aluminum","Circumaural Bowls","1695");

INSERT INTO  "store" VALUES (1,"Laurel Canyon","Valley Village","None","October 29, 2005");
INSERT INTO  "store" VALUES (2,"Woodman","Valley Glen","None","October 29, 2005");
INSERT INTO  "store" VALUES (3,"Sepulveda","Van Nuys","1,205 Spaces","October 29, 2005");
INSERT INTO  "store" VALUES (4,"Woodley","Van Nuys","None","October 29, 2005");
INSERT INTO  "store" VALUES (5,"Reseda","Tarzana","522 Spaces","October 29, 2005");
INSERT INTO  "store" VALUES (6,"Tampa","Tarzana","n/a","October 29, 2005");
INSERT INTO  "store" VALUES (7,"Pierce College","Winnetka","373 Spaces","October 29, 2005");
INSERT INTO  "store" VALUES (8,"Sherman Way","Canoga Park","Park & Ride Lot","June 30, 2012");
INSERT INTO  "store" VALUES (9,"Roscoe","Canoga Park","None","June 30, 2012");

CREATE TABLE "stock" (
"Store_ID" int,
"Headphone_ID" int,
"Quantity" int,
PRIMARY KEY ("Store_ID","Headphone_ID"),
FOREIGN KEY (`Store_ID`) REFERENCES `store`(`Store_ID`),
FOREIGN KEY (`Headphone_ID`) REFERENCES `headphone`(`Headphone_ID`)
);

INSERT INTO  "stock" VALUES (1,6,100);
INSERT INTO  "stock" VALUES (2,2,170);
INSERT INTO  "stock" VALUES (3,1,34);
INSERT INTO  "stock" VALUES (4,3,50);
INSERT INTO  "stock" VALUES (5,5,100);
INSERT INTO  "stock" VALUES (7,4,116);
INSERT INTO  "stock" VALUES (3,4,14);
INSERT INTO  "stock" VALUES (2,3,300);

