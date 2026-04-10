
PRAGMA foreign_keys = ON;

CREATE TABLE "participants" (
"id" int,
"name" text,
"popularity" real,
primary key ("id")
);


CREATE TABLE "songs" (
"id" int,
"language" text,
"original_artist" text,
"name" text,
"english_translation" text,
primary key ("id")
);

CREATE TABLE "performance_score" (
"participant_id" int,
"songs_id" int,
"voice_sound_quality" real,
"rhythm_tempo" real,
"stage_presence" real,
primary key ("participant_id", "songs_id"),
foreign key("participant_id") references "participants"("id"),
foreign key("songs_id") references "songs"("id")
);

INSERT INTO  "participants" VALUES ("1","Freeway","30.71");
INSERT INTO  "participants" VALUES ("2","Biby Michael's Friend","7.47");
INSERT INTO  "participants" VALUES ("3","Iskren Petsov","5.81");
INSERT INTO  "participants" VALUES ("4","Sunay Chalakov","53.11");
INSERT INTO  "participants" VALUES ("5","Tsetso Vlaykov","2.90");


INSERT INTO  "songs" VALUES ("1","English , Russian","Sasha Son"," Love ","—");
INSERT INTO  "songs" VALUES ("2","English , Hebrew , Arabic","Noa and Mira Awad"," There Must Be Another Way ","—");
INSERT INTO  "songs" VALUES ("3","French","Patricia Kaas"," Et s\'il fallait le faire ","And if it had to be done");
INSERT INTO  "songs" VALUES ("4","French , English","Malena Ernman"," La voix ","The voice");
INSERT INTO  "songs" VALUES ("5","Croatian","Igor Cukrov feat. Andrea"," Lijepa Tena ","Beautiful Tena");
INSERT INTO  "songs" VALUES ("6","Portuguese","Flor-de-Lis"," Todas as ruas do amor ","All the streets of love");
INSERT INTO  "songs" VALUES ("7","English","Yohanna"," Is It True? ","—");
INSERT INTO  "songs" VALUES ("8","English","Sakis Rouvas"," This Is Our Night ","—");
INSERT INTO  "songs" VALUES ("9","English , Armenian","Inga and Anush"," Jan Jan ","My dear");
INSERT INTO  "songs" VALUES ("10","Russian , Ukrainian","Anastasiya Prikhodko"," Mamo (Мамо)","Mum");
INSERT INTO  "songs" VALUES ("11","English","AySel and Arash"," Always ","—");
INSERT INTO  "songs" VALUES ("12","Bosnian","Regina"," Bistra voda ","Clear water");
INSERT INTO  "songs" VALUES ("13","Romanian , English","Nelly Ciobanu"," Hora din Moldova ","Dance from Moldova");
INSERT INTO  "songs" VALUES ("14","English","Chiara"," What If We ","—");
INSERT INTO  "songs" VALUES ("15","Estonian","Urban Symphony"," Rändajad ","Nomads");
INSERT INTO  "songs" VALUES ("16","English","Niels Brinck"," Believe Again ","—");
INSERT INTO  "songs" VALUES ("17","English","Alex Swings Oscar Sings!"," Miss Kiss Kiss Bang ","—");
INSERT INTO  "songs" VALUES ("18","English","Hadise"," Düm Tek Tek ","— [A]");
INSERT INTO  "songs" VALUES ("19","English","Kejsi Tola"," Carry Me in Your Dreams ","—");
INSERT INTO  "songs" VALUES ("20","English","Alexander Rybak"," Fairytale ","—");
INSERT INTO  "songs" VALUES ("21","English","Svetlana Loboda"," Be My Valentine ","—");
INSERT INTO  "songs" VALUES ("22","English","Elena"," The Balkan Girls ","—");
INSERT INTO  "songs" VALUES ("23","English","Jade Ewen"," It is My Time ","—");
INSERT INTO  "songs" VALUES ("24","English","Waldo\'s People"," Lose Control ","—");
INSERT INTO  "songs" VALUES ("25","Spanish , English","Soraya Arnelas"," La noche es para mi ","The night is for me");


INSERT INTO "performance_score" VALUES ("1", 13, 10, 9, 8);
INSERT INTO "performance_score" VALUES ("1", 12, 8, 8, 8);
INSERT INTO "performance_score" VALUES ("2", 22, 7, 4, 5);
INSERT INTO "performance_score" VALUES ("2", 23, 2,5,10);
INSERT INTO "performance_score" VALUES ("3", 5, 8, 7,8);
INSERT INTO "performance_score" VALUES ("3", 7, 7,10, 8);
INSERT INTO "performance_score" VALUES ("4", 18, 9, 9, 7);
INSERT INTO "performance_score" VALUES ("4", 7,6,8,9);
INSERT INTO "performance_score" VALUES ("4", 22,10,10,10);
INSERT INTO "performance_score" VALUES ("5", 25,9,8,6);

