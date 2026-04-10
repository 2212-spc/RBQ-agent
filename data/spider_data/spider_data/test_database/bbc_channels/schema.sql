PRAGMA foreign_keys = ON;

CREATE TABLE "channel" (
"Channel_ID" int,
"Name" text,
"Analogue_terrestrial_channel" text,
"Digital_terrestrial_channel" text,
"Internet" text,
PRIMARY KEY ("Channel_ID")
);


CREATE TABLE "director" (
"Director_ID" int,
"Name" text,
"Age" int,
PRIMARY KEY ("Director_ID")
);

INSERT INTO  "channel" VALUES ("1","BBC One","1","HD","bbc.co.uk");
INSERT INTO  "channel" VALUES ("2","ITV","3","HD","ITV - itv.com");
INSERT INTO  "channel" VALUES ("3","BBC Two","2","2","bbc.co.uk");
INSERT INTO  "channel" VALUES ("4","Channel 4","4","8","channel4.com");
INSERT INTO  "channel" VALUES ("5","Channel 5","5","44","unavailable");
INSERT INTO  "channel" VALUES ("6","ITV3","unavailable","10","itv.com");
INSERT INTO  "channel" VALUES ("7","ITV2","unavailable","6","itv.com");
INSERT INTO  "channel" VALUES ("8","E4","unavailable","28","e4.com");
INSERT INTO  "channel" VALUES ("9","Sky Sports 1","unavailable","unavailable","skysports.com");
INSERT INTO  "channel" VALUES ("10","Sky1","unavailable","unavailable","sky.com");
INSERT INTO  "channel" VALUES ("11","CBeebies","unavailable","71","bbc.co.uk");
INSERT INTO  "channel" VALUES ("12","ITV4","unavailable","24","itv.com");
INSERT INTO  "channel" VALUES ("13","BBC Three","unavailable","7","bbc.co.uk");
INSERT INTO  "channel" VALUES ("14","Dave","unavailable","12","dave.uktv.co.uk");


INSERT INTO  "director" VALUES (1,"DeSean Jackson","60");
INSERT INTO  "director" VALUES (2,"Hank Baskett","90");
INSERT INTO  "director" VALUES (3,"Greg Lewis","52");
INSERT INTO  "director" VALUES (4,"Brent Celek","44");
INSERT INTO  "director" VALUES (5,"Correll Buckhalter","59");
INSERT INTO  "director" VALUES (6,"Reggie Brown","40");
INSERT INTO  "director" VALUES (7,"Brian Westbrook","47");
INSERT INTO  "director" VALUES (8,"Jason Avant","31");
INSERT INTO  "director" VALUES (9,"Kevin Curtis","32");
INSERT INTO  "director" VALUES (10,"L.J. Smith","43");


CREATE TABLE "program" (
"Program_ID" int,
"Start_Year" real,
"Title" text,
"Director_ID" int,
"Channel_ID" int,
PRIMARY KEY ("Program_ID"),
FOREIGN KEY ("Director_ID") REFERENCES "director"("Director_ID"),
FOREIGN KEY ("Channel_ID") REFERENCES "channel"("Channel_ID")
);


INSERT INTO  "program" VALUES (1,"2002","The Angry Brigade",1,14);
INSERT INTO  "program" VALUES (2,"2006","Dracula",2,10);
INSERT INTO  "program" VALUES (3,"2006","Another Country",3,3);
INSERT INTO  "program" VALUES (4,"2007","Caesar III: An Empire Without End",5,14);
INSERT INTO  "program" VALUES (5,"2008","Othello",3,7);
INSERT INTO  "program" VALUES (6,"2008","The Leopard",6,7);
INSERT INTO  "program" VALUES (7,"2008","Cyrano de Bergerac",10,14);
INSERT INTO  "program" VALUES (8,"2009","Carnival",9,10);


CREATE TABLE "director_admin" (
"Director_ID" int,
"Channel_ID" int,
"Is_first_director" bool,
PRIMARY KEY ("Director_ID","Channel_ID"),
FOREIGN KEY ("Director_ID") REFERENCES "director"("Director_ID"),
FOREIGN KEY ("Channel_ID") REFERENCES "channel"("Channel_ID")
);
INSERT INTO  "director_admin" VALUES (1,14,"T");
INSERT INTO  "director_admin" VALUES (5,14,"F");
INSERT INTO  "director_admin" VALUES (3,14,"F");
INSERT INTO  "director_admin" VALUES (4,7,"T");
INSERT INTO  "director_admin" VALUES (6,7,"F");

