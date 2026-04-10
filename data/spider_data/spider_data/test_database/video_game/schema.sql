
PRAGMA foreign_keys = ON;

CREATE TABLE "platform" (
"Platform_ID" int,
"Platform_name" text,
"Market_district" text,
"Download_rank" int,
PRIMARY KEY ("Platform_ID")
);
INSERT INTO  "platform" VALUES (1,"Game Boy","Asia",2);
INSERT INTO  "platform" VALUES (2,"SNES","USA",3);
INSERT INTO  "platform" VALUES (3,"PlayStation","Europe",1);
INSERT INTO  "platform" VALUES (4,"Nintendo 64","Brazil",4);


CREATE TABLE "game" (
"Game_ID" int,
"Title" text,
"Release_Date" text,
"Franchise" text,
"Developers" text,
"Platform_ID" int,
"Units_sold_Millions" int,
PRIMARY KEY ("Game_ID"),
FOREIGN KEY ("Platform_ID") REFERENCES platform("Platform_ID")
);

CREATE TABLE "player" (
"Player_ID" int,
"Rank_of_the_year" int,
"Player_name" text,
"Position" text,
"College" text,
PRIMARY KEY ("Player_ID")
);

INSERT INTO  "game" VALUES ("1","Pokémon Red / Green / Blue Version","27 February 1996","Pokémon","Nintendo / GameFreak",1,"31.37");
INSERT INTO  "game" VALUES ("2","Pokémon Gold / Silver Version","21 November 1999","Pokémon","Nintendo/GameFreak",1,"23.10");
INSERT INTO  "game" VALUES ("3","Super Mario World","21 November 1990","Super Mario Bros.","Nintendo",2,"20.61");
INSERT INTO  "game" VALUES ("4","Pokémon Yellow: Special Pikachu Edition","12 September 1998","Pokémon","Nintendo/GameFreak",1,"14.64");
INSERT INTO  "game" VALUES ("5","Super Mario 64","23 June 1996","Super Mario Bros.","Nintendo",3,"11.89");
INSERT INTO  "game" VALUES ("6","Super Mario Land 2: 6 Golden Coins","21 October 1992","Super Mario Bros.","Nintendo",1,"11.18");
INSERT INTO  "game" VALUES ("7","Gran Turismo","23 December 1997","Gran Turismo","Polyphony Digital",4,"11.15");
INSERT INTO  "game" VALUES ("8","Super Mario All-Stars","14 July 1993","Super Mario Bros.","Nintendo",2,"10.55");
INSERT INTO  "game" VALUES ("9","Mario Kart 64","14 December 1996","Mario Kart","Nintendo",3,"9.87");


INSERT INTO  "player" VALUES ("1976","1","Lee Roy Selmon","Defensive end","Oklahoma");
INSERT INTO  "player" VALUES ("1977","1","Ricky Bell *","Running back","USC");
INSERT INTO  "player" VALUES ("1978","17","Doug Williams","Quarterback","Grambling");
INSERT INTO  "player" VALUES ("1980","22","Ray Snell","Guard","Wisconsin");
INSERT INTO  "player" VALUES ("1981","7","Hugh Green","Linebacker","Pittsburgh");
INSERT INTO  "player" VALUES ("1982","18","Sean Farrell","Guard","Penn State");
INSERT INTO  "player" VALUES ("1985","8","Ron Holmes","Defensive end","Washington");
INSERT INTO  "player" VALUES ("1986","1","Bo Jackson *","Running back","Auburn");
INSERT INTO  "player" VALUES ("1987","1","Vinny Testaverde *","Quarterback","Miami");
INSERT INTO  "player" VALUES ("1988","4","Paul Gruber","Offensive tackle","Wisconsin");
INSERT INTO  "player" VALUES ("1989","6","Broderick Thomas","Linebacker","Nebraska");
INSERT INTO  "player" VALUES ("1990","4","Keith McCants","Linebacker","Alabama");
INSERT INTO  "player" VALUES ("1991","7","Charles McRae","Offensive tackle","Tennessee");
INSERT INTO  "player" VALUES ("1993","6","Eric Curry","Defensive end","Alabama");
INSERT INTO  "player" VALUES ("1994","6","Trent Dilfer","Quarterback","Fresno State");
INSERT INTO  "player" VALUES ("1995","12","Warren Sapp †","Defensive tackle","Miami");
INSERT INTO  "player" VALUES ("1996","12","Regan Upshaw","Defensive end","California");
INSERT INTO  "player" VALUES ("1997","12","Warrick Dunn","Running back","Florida State");
INSERT INTO  "player" VALUES ("2004","15","Michael Clayton","Wide receiver","LSU");
INSERT INTO  "player" VALUES ("2005","5","Carnell Williams","Running Back","Auburn");
INSERT INTO  "player" VALUES ("2006","23","Davin Joseph","Guard","Oklahoma");


CREATE TABLE "game_player" (
"Player_ID" int,
"Game_ID" int,
"If_active" bool,
PRIMARY KEY ("Player_ID","Game_ID"),
FOREIGN KEY ("Player_ID") REFERENCES player("Player_ID"),
FOREIGN KEY ("Game_ID") REFERENCES game("Game_ID")
);

INSERT INTO  "game_player" VALUES ("1976",1,"F");
INSERT INTO  "game_player" VALUES ("1976",2,"T");
INSERT INTO  "game_player" VALUES ("2006",3,"T");
INSERT INTO  "game_player" VALUES ("2005",4,"T");
INSERT INTO  "game_player" VALUES ("1981",3,"T");
INSERT INTO  "game_player" VALUES ("1986",1,"F");
INSERT INTO  "game_player" VALUES ("1997",2,"T");
INSERT INTO  "game_player" VALUES ("1997",3,"T");
INSERT INTO  "game_player" VALUES ("1997",4,"T");
INSERT INTO  "game_player" VALUES ("1996",3,"T");


