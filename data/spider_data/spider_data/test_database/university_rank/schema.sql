
PRAGMA foreign_keys = ON;

CREATE TABLE "university" (
"University_ID" int,
"University_Name" text,
"City" text,
"State" text,
"Team_Name" text,
"Affiliation" text,
"Enrollment" int,
"Home_Conference" text,
PRIMARY KEY ("University_ID")
);

INSERT INTO  "university" VALUES (1,"Augustana College","Rock Island","Illinois","Vikings","Private_Lutheran","2500","CCIW");
INSERT INTO  "university" VALUES (2,"Aurora University","Aurora","Illinois","Spartans","Private_Non-sectarian","4400","Northern");
INSERT INTO  "university" VALUES (3,"Beloit College","Beloit","Wisconsin","Buccaneers","Private_United Church of Christ","1000","Midwest");
INSERT INTO  "university" VALUES (4,"Benedictine University","Lisle","Illinois","Eagles","Private_Catholic","1300","Northern");
INSERT INTO  "university" VALUES (5,"Carroll University ","Waukesha","Wisconsin","Pioneers","Private_Presbyterian","2789","Midwest");
INSERT INTO  "university" VALUES (6,"Carthage College","Kenosha","Wisconsin","Red Men","Private_Lutheran","2188","CCIW");
INSERT INTO  "university" VALUES (7,"Concordia University Wisconsin","Mequon","Wisconsin","Falcons","Private_Lutheran","1608","Northern");
INSERT INTO  "university" VALUES (8,"Cornell College","Mount Vernon","Iowa","Rams","Private_United Methodist","1176","Midwest");
INSERT INTO  "university" VALUES (9,"Defiance College","Defiance","Ohio","Yellow Jackets","Private_United Church of Christ","1000","HCAC");
INSERT INTO  "university" VALUES (10,"Elmhurst College","Elmhurst","Illinois","Bluejays","Private_United Church of Christ","3400","CCIW");
INSERT INTO  "university" VALUES (11,"Fontbonne University","St. Louis","Missouri","Griffins","Private_Catholic","2924","SLIAC");
INSERT INTO  "university" VALUES (12,"Hanover College","Hanover","Indiana","Panthers","Private_Presbyterian","975","HCAC");
INSERT INTO  "university" VALUES (13,"Milwaukee School of Engineering","Milwaukee","Wisconsin","Raiders","Private_Non-sectarian","1929","Northern");


CREATE TABLE "overall_ranking" (
"Rank" int,
"University_ID" int,
"Reputation_point" int,
"Research_point" int,
"Citation_point" int,
"Total" int,
PRIMARY KEY ("University_ID"),
FOREIGN KEY (`University_ID`) REFERENCES `university`(`University_ID`)
);

INSERT INTO  "overall_ranking" VALUES ("1",1,"5","2","0","7");
INSERT INTO  "overall_ranking" VALUES ("1",2,"5","1","1","7");
INSERT INTO  "overall_ranking" VALUES ("3",3,"4","0","0","4");
INSERT INTO  "overall_ranking" VALUES ("4",4,"1","3","2","6");
INSERT INTO  "overall_ranking" VALUES ("5",5,"1","2","0","3");
INSERT INTO  "overall_ranking" VALUES ("6",6,"1","0","2","3");
INSERT INTO  "overall_ranking" VALUES ("7",7,"1","0","1","2");
INSERT INTO  "overall_ranking" VALUES ("7",8,"1","0","1","2");
INSERT INTO  "overall_ranking" VALUES ("9",9,"1","0","0","1");
INSERT INTO  "overall_ranking" VALUES ("9",10,"1","0","0","1");
INSERT INTO  "overall_ranking" VALUES ("9",11,"1","0","0","1");
INSERT INTO  "overall_ranking" VALUES ("9",12,"1","0","0","1");
INSERT INTO  "overall_ranking" VALUES ("13",13,"0","0","1","1");

CREATE TABLE "major" (
"Major_ID" int,
"Major_Name" text,
"Major_Code" int,
PRIMARY KEY ("Major_ID")
);
INSERT INTO  "major" VALUES (1,"Accounting",1054);
INSERT INTO  "major" VALUES (2,"Advertising",1053);
INSERT INTO  "major" VALUES (3,"Healthcare Management",1154);
INSERT INTO  "major" VALUES (4,"Journalism",1059);
INSERT INTO  "major" VALUES (5,"Urban Education",1041);



CREATE TABLE "major_ranking" (
"Rank" int,
"University_ID" int,
"Major_ID" int,
PRIMARY KEY ("Rank","Major_ID","University_ID"),
FOREIGN KEY (`University_ID`) REFERENCES `university`(`University_ID`),
FOREIGN KEY (`Major_ID`) REFERENCES `major`(`Major_ID`)
);

INSERT INTO  "major_ranking" VALUES (1,1,1);
INSERT INTO  "major_ranking" VALUES (2,1,5);
INSERT INTO  "major_ranking" VALUES (1,2,3);
INSERT INTO  "major_ranking" VALUES (2,1,3);
INSERT INTO  "major_ranking" VALUES (1,3,1);
INSERT INTO  "major_ranking" VALUES (4,4,1);
INSERT INTO  "major_ranking" VALUES (3,2,4);
INSERT INTO  "major_ranking" VALUES (2,1,4);

