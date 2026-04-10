PRAGMA foreign_keys = ON;

CREATE TABLE "club" (
"Club_ID" int,
"Name" text,
"Manager" text,
"Captain" text,
"Manufacturer" text,
"Sponsor" text,
PRIMARY KEY ("Club_ID")
);

CREATE TABLE "player" (
"Player_ID" real,
"Name" text,
"Country" text,
"Earnings" real,
"Events_number" int,
"Wins_count" int,
"Club_ID" int,
PRIMARY KEY ("Player_ID"),
FOREIGN KEY ("Club_ID") REFERENCES "club"("Club_ID")
);

INSERT INTO  "club" VALUES (1,"Arsenal","Arsène Wenger","Cesc Fàbregas","Nike","Fly Emirates");
INSERT INTO  "club" VALUES (2,"Aston Villa","Martin O'Neill","Martin Laursen","Nike","Acorns");
INSERT INTO  "club" VALUES (3,"Blackburn Rovers","Sam Allardyce","Ryan Nelsen","Umbro","Crown Paints");
INSERT INTO  "club" VALUES (4,"Bolton Wanderers","Gary Megson","Kevin Davies","Reebok","Reebok");
INSERT INTO  "club" VALUES (5,"Chelsea","Guus Hiddink","John Terry","adidas","Samsung");
INSERT INTO  "club" VALUES (6,"Everton","David Moyes","Phil Neville","Umbro","Chang");
INSERT INTO  "club" VALUES (7,"Fulham","Roy Hodgson","Danny Murphy","Nike","LG");
INSERT INTO  "club" VALUES (8,"Hull City","Phil Brown","Ian Ashbee","Umbro","Karoo (H) / Kingston Communications (A, 3rd)");
INSERT INTO  "club" VALUES (9,"Liverpool","Rafael Benítez","Steven Gerrard","adidas","Carlsberg");


INSERT INTO  "player" VALUES ("1","Nick Price","Zimbabwe","1478557","18","4",1);
INSERT INTO  "player" VALUES ("2","Paul Azinger","United States","1458456","24","3",3);
INSERT INTO  "player" VALUES ("3","Greg Norman","Australia","1359653","15","2",5);
INSERT INTO  "player" VALUES ("4","Jim Gallagher, Jr.","United States","1078870","27","2",6);
INSERT INTO  "player" VALUES ("5","David Frost","South Africa","1030717","22","2",7);

