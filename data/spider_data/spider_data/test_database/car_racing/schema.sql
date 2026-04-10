PRAGMA foreign_keys = ON;


CREATE TABLE "country" (
"Country_Id" int,
"Country" text,
"Capital" text,
"Official_native_language" text,
"Regoin" text,
PRIMARY KEY ("Country_Id")
);

INSERT INTO  "country" VALUES (1,"Japan","Tokyo","Japanese","Asia");
INSERT INTO  "country" VALUES (2,"USA","Washington","English","North America");
INSERT INTO  "country" VALUES (6,"Britain","London","British English","Europe");
INSERT INTO  "country" VALUES (3,"China","Beijing","Chinese","Asia");
INSERT INTO  "country" VALUES (4,"Ireland","Dublin","Irish English","Europe");
INSERT INTO  "country" VALUES (5,"Isle of Man","Douglas","English Manx","Europe");



CREATE TABLE `team` (
"Team_ID" int,
"Team" text,
"Make" text,
"Manager" text,
"Sponsor" text,
"Car_Owner" text,
PRIMARY KEY ("Team_ID")
);

CREATE TABLE `driver` (
"Driver_ID" int,
"Driver" text,
"Country" int,
"Age" int,
"Car_#" real,
"Make" text,
"Points" text,
"Laps" real,
"Winnings" text,
PRIMARY KEY ("Driver_ID"),
FOREIGN KEY (`Country`) REFERENCES `country`(`Country_ID`)
);



CREATE TABLE `team_driver` (
"Team_ID" int,
"Driver_ID" int,
PRIMARY KEY ("Team_ID","Driver_ID"),
FOREIGN KEY (`Team_ID`) REFERENCES `team`(`Team_ID`),
FOREIGN KEY (`Driver_ID`) REFERENCES `driver`(`Driver_ID`)
);


INSERT INTO  "team" VALUES (1,"Arrington Racing","Chrysler Imperial","Buddy Arrington","Arrington Racing","Buddy Arrington");
INSERT INTO  "team" VALUES (2,"Benfield Racing","Buick Regal","Joe Ruttman","Levi Garrett","Ron Benfield");
INSERT INTO  "team" VALUES (3,"Blue Max Racing","Pontiac Grand Prix","Tim Richmond","Old Milwaukee","Raymond Beadle");
INSERT INTO  "team" VALUES (4,"Bobby Hawkins Racing","Chevrolet Monte Carlo","David Pearson","Chattanooga Chew","Bobby Hawkins");
INSERT INTO  "team" VALUES (5,"Bud Moore Engineering","Ford Thunderbird","Dale Earnhardt","Wrangler Jeans","Bud Moore");
INSERT INTO  "team" VALUES (6,"Cliff Stewart Racing","Pontiac Grand Prix","Geoff Bodine","Gatorade","Cliff Stewart");
INSERT INTO  "team" VALUES (7,"DiGard Motorsports","Buick Regal","Bobby Allison","Miller American","Bill Gardner");
INSERT INTO  "team" VALUES (8,"Donlavey Racing","Ford Thunderbird","Dick Brooks","Chameleon Sunglasses","Junie Donlavey");
INSERT INTO  "team" VALUES (9,"Ellington Racing","Chevrolet Monte Carlo","Lake Speed","UNO / Bull Frog Knits","Hoss Ellington");
INSERT INTO  "team" VALUES (10,"Hagan Racing","Chevrolet Monte Carlo","Terry Labonte","Budweiser","Billy Hagan");
INSERT INTO  "team" VALUES (11,"Hamby Motorsports","Pontiac Grand Prix","Sterling Marlin (R)","Hesco Exhaust Systems","Roger Hamby");
INSERT INTO  "team" VALUES (12,"Henderson Motorsports","Chevrolet Monte Carlo Buick Regal","Ronnie Hopkins (R)","Food Country USA","Charlie Henderson");

INSERT INTO  "driver" VALUES (1,"Kasey Kahne",2,23,"9","Dodge","185","334","$530,164");
INSERT INTO  "driver" VALUES (2,"Matt Kenseth",2,21,"17","Ford","175","334","$362,491");
INSERT INTO  "driver" VALUES (3,"Tony Stewart",2,19,"20","Chevrolet","175","334","$286,386");
INSERT INTO  "driver" VALUES (4,"Denny Hamlin *",2,25,"11","Chevrolet","165","334","$208,500");
INSERT INTO  "driver" VALUES (5,"Kevin Li",3,23,"29","Chevrolet","160","334","$204,511");
INSERT INTO  "driver" VALUES (6,"Jeff Chen",3,25,"31","Chevrolet","150","334","$172,220");
INSERT INTO  "driver" VALUES (7,"Scott Riggs",1,22,"10","Dodge","146","334","$133,850");
INSERT INTO  "driver" VALUES (8,"Mali Lu Jr. *",3,29,"1","Chevrolet","147","334","$156,608");
INSERT INTO  "driver" VALUES (9,"Mark Martin",5,21,"6","Ford","143","334","$151,850");
INSERT INTO  "driver" VALUES (10,"Bobby Labonte",4,25,"43","Dodge","134","334","$164,211");

INSERT INTO  "team_driver" VALUES (1,1);
INSERT INTO  "team_driver" VALUES (2,3);
INSERT INTO  "team_driver" VALUES (1,5);
INSERT INTO  "team_driver" VALUES (5,4);
INSERT INTO  "team_driver" VALUES (1,9);
INSERT INTO  "team_driver" VALUES (1,10);
INSERT INTO  "team_driver" VALUES (10,7);
INSERT INTO  "team_driver" VALUES (9,6);
INSERT INTO  "team_driver" VALUES (1,2);
INSERT INTO  "team_driver" VALUES (1,8);

