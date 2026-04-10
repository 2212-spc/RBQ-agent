
PRAGMA foreign_keys = ON;

CREATE TABLE "conference" (
"Conference_ID" int,
"Conference_Name" text,
"Year" int,
"Location" text,
PRIMARY KEY ("Conference_ID")
);

INSERT INTO  "conference" VALUES (1,"ACL","2003","Philippines");
INSERT INTO  "conference" VALUES (2,"ACL","2004","Philippines");
INSERT INTO  "conference" VALUES (3,"Naccl","2003","Japan");
INSERT INTO  "conference" VALUES (4,"Naccl","2004","China");
INSERT INTO  "conference" VALUES (5,"AICS","2003","England");
INSERT INTO  "conference" VALUES (6,"AICS","2004","USA");


CREATE TABLE institution (
"Institution_ID" int,
"Institution_Name" text,
"Location" text,
"Founded" int,
PRIMARY KEY ("Institution_ID")
);

INSERT INTO  institution VALUES (1,"Illinois State University","Normal, Illinois","1857");
INSERT INTO  institution VALUES (2,"Bradley University","Peoria, Illinois","1897");
INSERT INTO  institution VALUES (3,"Eureka College","Eureka, Illinois","1855");
INSERT INTO  institution VALUES (4,"Hedding College (defunct)","Abingdon, Illinois","1855");
INSERT INTO  institution VALUES (5,"Illinois College","Jacksonville, Illinois","1829");
INSERT INTO  institution VALUES (6,"Illinois Wesleyan University","Bloomington, Illinois","1850");
INSERT INTO  institution VALUES (7,"Lincoln College, Illinois","Lincoln, Illinois","1865");
INSERT INTO  institution VALUES (8,"Lombard College (defunct)","Galesburg, Illinois","1853");
INSERT INTO  institution VALUES (9,"Millikin University","Decatur, Illinois","1901");
INSERT INTO  institution VALUES (10,"Shurtleff College (defunct)","Alton, Illinois","1827");


CREATE TABLE "staff" (
"staff_ID" int,
"name" text,
"Age" int,
"Nationality" text,
"Institution_ID" int,
PRIMARY KEY ("staff_ID"),
FOREIGN KEY (`Institution_ID`) REFERENCES `institution`(`Institution_ID`)
);


INSERT INTO  "staff" VALUES (1,"Bobby Jackson","24","United States",1);
INSERT INTO  "staff" VALUES (2,"Casey Jacobsen","23","United States",2);
INSERT INTO  "staff" VALUES (3,"Alexander Johnson","42","United Kindom",3);
INSERT INTO  "staff" VALUES (4,"Chris Johnson","34","Canada",4);
INSERT INTO  "staff" VALUES (5,"Bobby Jones","28","United States",5);
INSERT INTO  "staff" VALUES (6,"Dahntay Jones","30","United Kindom",10);
INSERT INTO  "staff" VALUES (7,"Damon Jones","41","United Kindom",8);



CREATE TABLE "conference_participation" (
"Conference_ID" int,
"staff_ID" int,
"role" text,
PRIMARY KEY ("staff_ID","Conference_ID"),
FOREIGN KEY (`staff_ID`) REFERENCES `staff`(`staff_ID`),
FOREIGN KEY (`Conference_ID`) REFERENCES `conference`(`Conference_ID`)
);

INSERT INTO  "conference_participation" VALUES (1,6,"Speaker");
INSERT INTO  "conference_participation" VALUES (2,5,"Sponsor");
INSERT INTO  "conference_participation" VALUES (1,4,"Speaker");
INSERT INTO  "conference_participation" VALUES (1,2,"Sponsor");
INSERT INTO  "conference_participation" VALUES (2,7,"Speaker");
INSERT INTO  "conference_participation" VALUES (4,5,"Participant");
INSERT INTO  "conference_participation" VALUES (1,1,"Sponsor");
INSERT INTO  "conference_participation" VALUES (5,5,"Speaker");
INSERT INTO  "conference_participation" VALUES (6,5,"Participant");

