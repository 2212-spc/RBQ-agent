PRAGMA foreign_keys = ON;

CREATE TABLE "building" (
"Building_ID" int,
"Region_ID" int,
"Name" text,
"Address" text,
"Number_of_Stories" int,
"Completed_Year" int,
PRIMARY KEY ("Building_ID"),
FOREIGN KEY ("Region_ID") REFERENCES "region"("Region_ID")
);

CREATE TABLE "region" (
"Region_ID" int,
"Name" text,
"Capital" text,
"Area" int,
"Population" int,
PRIMARY KEY ("Region_ID")
);

INSERT INTO  "region" VALUES (1,"Abruzzo","L'Aquila","10763","1342177");
INSERT INTO  "region" VALUES (2,"Aosta Valley","Aosta","3263","128129");
INSERT INTO  "region" VALUES (3,"Apulia","Bari","19358","4090577");
INSERT INTO  "region" VALUES (4,"Basilicata","Potenza","9995","587680");
INSERT INTO  "region" VALUES (5,"Calabria","Catanzaro","15080","2011537");
INSERT INTO  "region" VALUES (6,"Campania","Naples","13590","5833131");
INSERT INTO  "region" VALUES (7,"Emilia-Romagna","Bologna","22446","4429766");
INSERT INTO  "region" VALUES (8,"Friuli-Venezia Giulia","Trieste","7858","1235761");
INSERT INTO  "region" VALUES (9,"Lazio","Rome","17236","5724365");
INSERT INTO  "region" VALUES (10,"Liguria","Genoa","5422","1616993");
INSERT INTO  "region" VALUES (11,"Lombardy","Milan","23844","9909348");

INSERT INTO  "building" VALUES ("1",1,"La Renaissance Apartments","424 Spadina Crescent E","24","1983");
INSERT INTO  "building" VALUES ("2",2,"Hallmark Place","311 6th Ave N","27","1984");
INSERT INTO  "building" VALUES ("3",4,"Saskatoon Square","410 22nd St E","17","1979");
INSERT INTO  "building" VALUES ("4",5,"The Terrace Apartments","315 5th Ave N","22","1980");
INSERT INTO  "building" VALUES ("5",6,"Radisson Hotel","405 20th St E","12","1983");
INSERT INTO  "building" VALUES ("6",8,"The View on Fifth","320 5th Ave N","22","1968");
INSERT INTO  "building" VALUES ("7",9,"The Luther","1223 Temperance St","9","1978");
INSERT INTO  "building" VALUES ("8",10,"Marquis Towers","241 5th Ave N","36","1966");

