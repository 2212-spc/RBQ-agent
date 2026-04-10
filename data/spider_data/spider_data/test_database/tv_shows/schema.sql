
PRAGMA foreign_keys = ON;

CREATE TABLE "city_channel" (
"ID" int,
"City" text,
"Station_name" text,
"Owned_Since" real,
"Affiliation" text,
PRIMARY KEY ("ID")
);

CREATE TABLE "radio" (
"Radio_ID" int,
"Transmitter" text,
"Radio_MHz" text,
"2FM_MHz" text,
"RnaG_MHz" text,
"Lyric_FM_MHz" text,
"ERP_kW" text,
PRIMARY KEY ("Radio_ID")
);

CREATE TABLE "tv_show" (
"tv_show_ID" int,
"tv_show_name" text,
"Sub_tittle" text,
"Next_show_name" text,
"Original_Airdate" text,
PRIMARY KEY ("tv_show_ID")
);

INSERT INTO  "city_channel" VALUES (1,"Phoenix","KNXV-TV","1985","ABC");
INSERT INTO  "city_channel" VALUES (2,"Bakersfield, California","KERO-TV","2011","ABC");
INSERT INTO  "city_channel" VALUES (3,"Bakersfield, California","KZKC-LP","2011","Azteca América");
INSERT INTO  "city_channel" VALUES (4,"San Diego","KGTV","2011","ABC");
INSERT INTO  "city_channel" VALUES (5,"San Diego","KZSD-LP","2011","Azteca América");
INSERT INTO  "city_channel" VALUES (6,"Colorado Springs, Colorado","KZKS-LP","2011","Azteca América");
INSERT INTO  "city_channel" VALUES (7,"Denver","KMGH-TV","2011","ABC");
INSERT INTO  "city_channel" VALUES (8,"Denver","KZCO-LP","2011","Azteca América");
INSERT INTO  "city_channel" VALUES (9,"Fort Collins, Colorado","KZFC-LP","2011","Azteca América");
INSERT INTO  "city_channel" VALUES (10,"Tampa – St. Petersburg","WFTS-TV","1986","ABC");
INSERT INTO  "city_channel" VALUES (11,"West Palm Beach","WPTV","1961","NBC");
INSERT INTO  "city_channel" VALUES (12,"Indianapolis","WRTV","2011","ABC");
INSERT INTO  "city_channel" VALUES (13,"Baltimore","WMAR-TV","1991","ABC");
INSERT INTO  "city_channel" VALUES (14,"Detroit","WXYZ-TV","1986","ABC");

INSERT INTO  "radio" VALUES (1,"Cairn Hill","89.8","N/A","N/A","N/A","16");
INSERT INTO  "radio" VALUES (2,"Clermont Carn","87.8","97.0","102.7","95.2","40");
INSERT INTO  "radio" VALUES (3,"Kippure","89.1","91.3","93.5","98.7","40");
INSERT INTO  "radio" VALUES (4,"Maghera","88.8","91.0","93.2","98.4","160");
INSERT INTO  "radio" VALUES (5,"Mount Leinster","89.6","91.8","94.0","99.2","100");
INSERT INTO  "radio" VALUES (6,"Mullaghanish","90.0","92.2","94.4","99.6","160");
INSERT INTO  "radio" VALUES (7,"Three Rock","88.5","90.7","92.9","96.7","12.5");

INSERT INTO  "tv_show" VALUES (1,"Peace and Quiet","Wanted: Wade","Garfield Goes an Hawaii","September17,1988");
INSERT INTO  "tv_show" VALUES (2,"Box O' Fun","Unidentified Flying Orson","School Daze","September24,1988");
INSERT INTO  "tv_show" VALUES (3,"Nighty Nightmare","Banana Nose","Ode to Odie","October1,1988");
INSERT INTO  "tv_show" VALUES (4,"Fraidy Cat","Shell Shocked Sheldon","Nothing to Sneeze At","October8,1988");
INSERT INTO  "tv_show" VALUES (5,"Garfield's Moving Experience","Wade: You're Afraid","Good Mouse-keeping","October15,1988");
INSERT INTO  "tv_show" VALUES (6,"Identity Crisis","The Bad Sport","Up a Tree","October22,1988");
INSERT INTO  "tv_show" VALUES (7,"Weighty Problem","The Worm Turns","Good Cat, Bad Cat","October29,1988");
INSERT INTO  "tv_show" VALUES (8,"Cabin Fever","Return of Power Pig","Fair Exchange","November5,1988");
INSERT INTO  "tv_show" VALUES (9,"The Binky Show","Keeping Cool","Don't Move","November12,1988");
INSERT INTO  "tv_show" VALUES (10,"Magic Mutt","Short Story","Monday Misery","November19,1988");
INSERT INTO  "tv_show" VALUES (11,"Best of Breed","National Tapioca Pudding Day","All About Odie","November26,1988");
INSERT INTO  "tv_show" VALUES (12,"Caped Avenger","Shy Fly Guy","Green Thumbs Down","December3,1988");


CREATE TABLE "city_channel_radio" (
"City_channel_ID" int,
"Radio_ID" int,
"Is_online" bool,
PRIMARY KEY ("City_channel_ID","Radio_ID"),
FOREIGN KEY (`City_channel_ID`) REFERENCES `city_channel`(`ID`),
FOREIGN KEY (`Radio_ID`) REFERENCES `radio`(`Radio_ID`)
);


INSERT INTO  "city_channel_radio" VALUES (1,1,"T");
INSERT INTO  "city_channel_radio" VALUES (2,2,"T");
INSERT INTO  "city_channel_radio" VALUES (3,3,"F");
INSERT INTO  "city_channel_radio" VALUES (4,4,"T");
INSERT INTO  "city_channel_radio" VALUES (10,1,"F");
INSERT INTO  "city_channel_radio" VALUES (6,1,"T");
INSERT INTO  "city_channel_radio" VALUES (7,5,"F");
INSERT INTO  "city_channel_radio" VALUES (8,3,"T");
INSERT INTO  "city_channel_radio" VALUES (4,6,"T");
INSERT INTO  "city_channel_radio" VALUES (12,2,"F");


CREATE TABLE "city_channel_tv_show" (
"City_channel_ID" int,
"tv_show_ID" int,
"Is_online" bool,
"Is_free" bool,
PRIMARY KEY ("City_channel_ID","tv_show_ID"),
FOREIGN KEY (`City_channel_ID`) REFERENCES `city_channel`(`ID`),
FOREIGN KEY (`tv_show_ID`) REFERENCES `tv_show`(`tv_show_ID`)
);

INSERT INTO  "city_channel_tv_show" VALUES (12,2,"T","F");
INSERT INTO  "city_channel_tv_show" VALUES (13,1,"T","F");
INSERT INTO  "city_channel_tv_show" VALUES (14,1,"F","F");
INSERT INTO  "city_channel_tv_show" VALUES (11,4,"T","T");
INSERT INTO  "city_channel_tv_show" VALUES (1,2,"T","F");
INSERT INTO  "city_channel_tv_show" VALUES (2,3,"F","F");
INSERT INTO  "city_channel_tv_show" VALUES (5,1,"T","T");
INSERT INTO  "city_channel_tv_show" VALUES (7,2,"T","T");
