
PRAGMA foreign_keys = ON;

CREATE TABLE "member" (
"Member_ID" int,
"Name" text,
"Nationality" text,
"Age" int,
PRIMARY KEY ("Member_ID")
);

CREATE TABLE "club" (
"Club_ID" int,
"Overall_Ranking" int,
"Team_Leader" text,
"Club_Name" text,
PRIMARY KEY ("Club_ID")
);

INSERT INTO  "member" VALUES ("1984","Wally Lewis","Australia",23);
INSERT INTO  "member" VALUES ("1985","Brett Kenny","Australia",19);
INSERT INTO  "member" VALUES ("1986","Garry Jack","Australia",18);
INSERT INTO  "member" VALUES ("1987","Hugh McGahan Peter Sterling","New Zealand Australia",24);
INSERT INTO  "member" VALUES ("1988","Ellery Hanley","England",19);
INSERT INTO  "member" VALUES ("1989","Mal Meninga","Australia",22);
INSERT INTO  "member" VALUES ("1990","Garry Schofield","England",21);
INSERT INTO  "member" VALUES ("1991","No award given","No award given",20);
INSERT INTO  "member" VALUES ("1999","Andrew Johns","Australia",19);
INSERT INTO  "member" VALUES ("2000","Brad Fittler","Australia",17);


INSERT INTO  "club" VALUES ("1","5","Mack Mitchell","Houston");
INSERT INTO  "club" VALUES ("3","57","Oscar Roan","SMU");
INSERT INTO  "club" VALUES ("4","82","Tony Peters","Oklahoma");
INSERT INTO  "club" VALUES ("5","109","John Zimba","Villanova");
INSERT INTO  "club" VALUES ("2","119","Jim Cope","Ohio State");
INSERT INTO  "club" VALUES ("6","150","Charles Miller","West Virginia");
INSERT INTO  "club" VALUES ("16","154","Henry Hynoski","Temple");
INSERT INTO  "club" VALUES ("7","161","Merle Wang","TCU");
INSERT INTO  "club" VALUES ("8","186","Barry Santini","Purdue");
INSERT INTO  "club" VALUES ("9","213","Larry Poole","Kent State");
INSERT INTO  "club" VALUES ("19","215","Floyd Hogan","Arkansas");
INSERT INTO  "club" VALUES ("10","238","Stan Lewis","Wayne");


CREATE TABLE "club_leader" (
"Club_ID" int,
"Member_ID" int,
"Year_Join" text,
PRIMARY KEY ("Club_ID","Member_ID"),
FOREIGN KEY ("Club_ID") REFERENCES "club"("Club_ID"),
FOREIGN KEY ("Member_ID") REFERENCES "member"("Member_ID")
);

INSERT INTO  "club_leader" VALUES (1,1988,"2018");
INSERT INTO  "club_leader" VALUES (8,1984,"2017");
INSERT INTO  "club_leader" VALUES (6,1985,"2015");
INSERT INTO  "club_leader" VALUES (4,1990,"2018");
INSERT INTO  "club_leader" VALUES (10,1991,"2017");
INSERT INTO  "club_leader" VALUES (6,1999,"2018");

