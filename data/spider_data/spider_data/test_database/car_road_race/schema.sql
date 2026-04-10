PRAGMA foreign_keys = ON;

CREATE TABLE "driver" (
"Driver_ID" int,
"Driver_Name" text,
"Entrant" text,
"Constructor" text,
"Chassis" text,
"Engine" text,
"Age" int,
PRIMARY KEY ("Driver_ID")
);

CREATE TABLE "race" (
"Road" int,
"Driver_ID" int,
"Race_Name" text,
"Pole_Position" text,
"Fastest_Lap" text,
"Winning_driver" text,
"Winning_team" text,
"Report" text,
PRIMARY KEY ("Road"),
FOREIGN KEY (`Driver_ID`) REFERENCES `driver`(`Driver_ID`)
);

INSERT INTO  "driver" VALUES ("1","Ernst-Günther Burggaller","German Bugatti Team","Bugatti","Bugatti T35B","2.3 L8","18");
INSERT INTO  "driver" VALUES ("2","Hermann zu Leiningen","German Bugatti Team","Bugatti","Bugatti T35C","2.0 L8","20");
INSERT INTO  "driver" VALUES ("3","Heinrich-Joachim von Morgen","German Bugatti Team","Bugatti","Bugatti T35B","2.3 L8","23");
INSERT INTO  "driver" VALUES ("4","Rudolf Caracciola","Private entry","Mercedes-Benz","Mercedes-Benz SSK L","7.1 L6","24");
INSERT INTO  "driver" VALUES ("5","Earl Howe","Private entry","Bugatti","Bugatti T51","2.3 L8","26");
INSERT INTO  "driver" VALUES ("6","Clifton Penn-Hughes","Private entry","Bugatti","Bugatti T35","2.0 L8","21");
INSERT INTO  "driver" VALUES ("7","Henry Birkin","Private entry","Maserati","Maserati 26M","2.5 L8","28");
INSERT INTO  "driver" VALUES ("8","Bernhard Ackerl","Private entry","Bugatti","Bugatti T37","1.5 L4","29");
INSERT INTO  "driver" VALUES ("9","Juan Zanelli","Private entry","Bugatti","Bugatti T35B","2.3 L8","26");
INSERT INTO  "driver" VALUES ("10","Guy Bouriat","Automobiles Ettore Bugatti","Bugatti","Bugatti T51","2.3 L8","28");
INSERT INTO  "driver" VALUES ("11","Louis Chiron","Automobiles Ettore Bugatti","Bugatti","Bugatti T51","2.3 L8","35");



INSERT INTO  "race" VALUES ("2","1","Monterey Festival of Speed","James Hinchcliffe","Douglas Soares","James Hinchcliffe","Forsythe Pettit Racing","Report");
INSERT INTO  "race" VALUES ("3","2","Sommet des Legends","Junior Strous","Junior Strous","Junior Strous","Condor Motorsports","Report");
INSERT INTO  "race" VALUES ("4","1","Rexall Grand Prix of Edmonton - Race 1","James Hinchcliffe","David Garza Pérez","Jonathan Bomarito","Mathiasen Motorsports","Report");
INSERT INTO  "race" VALUES ("5","3","Rexall Grand Prix of Edmonton - Race 2","Carl Skerlong","Carl Skerlong","Jonathan Summerton","Newman Wachs Racing","Report");
INSERT INTO  "race" VALUES ("6","4","Road Race Showcase/Road America - Race 1","Dane Cameron","Tõnis Kasemets","Jonathan Bomarito","Mathiasen Motorsports","Report");
INSERT INTO  "race" VALUES ("7","9","Road Race Showcase/Road America - Race 2","Jonathan Bomarito","Dane Cameron","Jonathan Summerton","Newman Wachs Racing","Report");
INSERT INTO  "race" VALUES ("8","10","Grand Prix de Trois-Rivières","Jonathan Bomarito","Jonathan Summerton","Jonathan Bomarito","Mathiasen Motorsports","Report");
INSERT INTO  "race" VALUES ("9","1","Mazda Formula Zoom Zoom","Carl Skerlong","Carl Skerlong","Carl Skerlong","Pacific Coast Motorsports","Report");
INSERT INTO  "race" VALUES ("10","2","SunRichGourmet.com 1000","Markus Niemelä","Carl Skerlong","Markus Niemelä","Brooks Associates Racing","Report");
