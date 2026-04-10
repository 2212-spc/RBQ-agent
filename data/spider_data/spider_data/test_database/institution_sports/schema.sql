PRAGMA foreign_keys = ON;

CREATE TABLE "institution" (
"Institution_ID" int,
"Name" text,
"Team" text,
"City" text,
"Province" text,
"Founded" real,
"Affiliation" text,
"Enrollment" real,
"Endowment" text,
"Stadium" text,
"Capacity" real,
PRIMARY KEY ("Institution_ID")
);

CREATE TABLE "Championship" (
"Institution_ID" int,
"Nickname" text,
"Joined" real,
"Number_of_Championships" real,
PRIMARY KEY ("Institution_ID"),
FOREIGN KEY ("Institution_ID") REFERENCES `institution`("Institution_ID")
);

INSERT INTO  "institution" VALUES (1,"University of British Columbia","Thunderbirds","Vancouver","BC","1908","Public","43579","$1.01B","Thunderbird Stadium","3500");
INSERT INTO  "institution" VALUES (2,"University of Calgary","Dinos","Calgary","AB","1966","Public","28196","$444M","McMahon Stadium","35650");
INSERT INTO  "institution" VALUES (3,"University of Alberta","Golden Bears","Edmonton","AB","1908","Public","36435","$751M","Foote Field","3500");
INSERT INTO  "institution" VALUES (4,"University of Saskatchewan","Huskies","Saskatoon","SK","1907","Public","19082","$136.7M","Griffiths Stadium","4997");
INSERT INTO  "institution" VALUES (5,"University of Regina","Rams","Regina","SK","1911","Public","12800","$25.9M","Mosaic Stadium","30048");

INSERT INTO  "Championship" VALUES (1,"Colonials","1993","0");
INSERT INTO  "Championship" VALUES (2,"Terrapins","1994","0");
INSERT INTO  "Championship" VALUES (3,"Wildcats","1995","1");
INSERT INTO  "Championship" VALUES (4,"Tar Heels","1995","5");

