PRAGMA foreign_keys = ON;

CREATE TABLE "book" (
"Book_ID" int,
"Title" text,
"Type" text,
"Pages" int,
"Chapters" int,
"Audio" text,
"Release" text,
PRIMARY KEY ("Book_ID")
);

CREATE TABLE "review" (
"Review_ID" int,
"Book_ID" int,
"Rating" real,
"Readers_in_Million" real,
"Rank" int,
PRIMARY KEY ("Review_ID"),
FOREIGN KEY ("Book_ID") REFERENCES "book"("Book_ID")
);

INSERT INTO  "book" VALUES (1,"A Game of Thrones","Novel","704","73","33h 53m","August 1996");
INSERT INTO  "book" VALUES (2,"A Clash of Kings","Novel","768","70","37h 17m","February 1999");
INSERT INTO  "book" VALUES (3,"A Storm of Swords","Novel","992","82","47h 37m","November 2000");
INSERT INTO  "book" VALUES (4,"A Feast for Crows","Novel","753","46","31h 10m","November 2005");
INSERT INTO  "book" VALUES (5,"A Dance with Dragons","Poet","1056","73","48h 56m","July 2011");

INSERT INTO  "review" VALUES (1,1,"6.6","3.3","16");
INSERT INTO  "review" VALUES (2,3,"5.7","2.8","25");
INSERT INTO  "review" VALUES (3,4,"5.8","2.6","26");
INSERT INTO  "review" VALUES (4,5,"5.6","2.4","35");

