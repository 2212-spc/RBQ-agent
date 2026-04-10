PRAGMA foreign_keys = ON;

CREATE TABLE "languages" (
"id" integer,
"name" text,
PRIMARY KEY ("id")
);

INSERT INTO  "languages" VALUES ("1","Icelandic");
INSERT INTO  "languages" VALUES ("2","Swedish");
INSERT INTO  "languages" VALUES ("3","English");
INSERT INTO  "languages" VALUES ("4","Danish");
INSERT INTO  "languages" VALUES ("5","Finnish");
INSERT INTO  "languages" VALUES ("6","German");
INSERT INTO  "languages" VALUES ("7","French");
INSERT INTO  "languages" VALUES ("8","Norwegian");
INSERT INTO  "languages" VALUES ("9","Italian");
INSERT INTO  "languages" VALUES ("10","Romansh");

CREATE TABLE "countries" (
"id" integer,
"name" text,
"overall_score" real,
"justice_score" real,
"health_score" real,
"education_score" real,
"economics_score" real,
"politics_score" real,
PRIMARY KEY ("id")
);




INSERT INTO  "countries" VALUES ("1","Iceland","100.0","100.0","90.5","96.7","88.0","92.8");
INSERT INTO  "countries" VALUES ("2","Sweden","99.2","90.8","94.8","95.5","90.3","93.1");
INSERT INTO  "countries" VALUES ("3","Canada","96.6","100.0","92.7","92.0","91.0","66.9");
INSERT INTO  "countries" VALUES ("4","Denmark","95.3","86.1","94.9","97.6","88.5","78.4");
INSERT INTO  "countries" VALUES ("5","Finland","92.8","80.2","91.4","91.3","86.8","100.0");
INSERT INTO  "countries" VALUES ("6","Switzerland","91.9","87.9","94.4","97.3","82.6","74.6");
INSERT INTO  "countries" VALUES ("7","Norway","91.3","79.3","100.0","74.0","93.5","93.9");
INSERT INTO  "countries" VALUES ("8","United States","89.8","82.9","92.8","97.3","83.9","68.6");
INSERT INTO  "countries" VALUES ("9","Australia","88.2","80.7","93.3","93.9","85.3","65.1");


CREATE TABLE "official_languages" (
"language_id" integer,
"country_id" integer,
PRIMARY KEY ("language_id", "country_id"),
FOREIGN KEY ("language_id") REFERENCES "languages"("id"),
FOREIGN KEY ("country_id") REFERENCES "countries"("id")
);



INSERT INTO  "official_languages" VALUES (1,1);
INSERT INTO  "official_languages" VALUES (2,2);
INSERT INTO  "official_languages" VALUES (3,3);
INSERT INTO  "official_languages" VALUES (4,4);
INSERT INTO  "official_languages" VALUES (5,5);
INSERT INTO  "official_languages" VALUES (6,6);
INSERT INTO  "official_languages" VALUES (7,6);
INSERT INTO  "official_languages" VALUES (9,6);
INSERT INTO  "official_languages" VALUES (10,6);
INSERT INTO  "official_languages" VALUES (8,7);
INSERT INTO  "official_languages" VALUES (3,8);
INSERT INTO  "official_languages" VALUES (3,9);

