PRAGMA foreign_keys = ON;

CREATE TABLE "vehicle" (
"Vehicle_ID" int,
"Model" text,
"Build_Year" text,
"Top_Speed" int,
"Power" int,
"Builder" text,
"Total_Production" text,
PRIMARY KEY ("Vehicle_ID")
);

CREATE TABLE "driver" (
"Driver_ID" int,
"Name" text,
"Citizenship" text,
"Racing_Series" text,
PRIMARY KEY ("Driver_ID")
);

INSERT INTO  "vehicle" VALUES (1,"AC4000","1996","120","4000","Zhuzhou","1");
INSERT INTO  "vehicle" VALUES (2,"DJ ","2000","200","4800","Zhuzhou","2");
INSERT INTO  "vehicle" VALUES (3,"DJ1","2000–2001","120","6400","Zhuzhou Siemens , Germany","20");
INSERT INTO  "vehicle" VALUES (4,"DJ2","2001","200","4800","Zhuzhou","3");
INSERT INTO  "vehicle" VALUES (5,"Tiansuo","2003","200","4800","Datong","1");
INSERT INTO  "vehicle" VALUES (6,"HXD1","2006–2010","120","9600","Zhuzhou Siemens , Germany","220");
INSERT INTO  "vehicle" VALUES (7,"HXD1.1","2012–","120","9600","Zhuzhou","50");
INSERT INTO  "vehicle" VALUES (8,"HXD1.6","2012","120","9600","Ziyang","1");


INSERT INTO  "driver" VALUES (1,"Jeff Gordon","United States","NASCAR");
INSERT INTO  "driver" VALUES (2,"Jimmie Johnson","United States","NASCAR");
INSERT INTO  "driver" VALUES (3,"Tony Stewart","United States","NASCAR");
INSERT INTO  "driver" VALUES (4,"Ryan Hunter-Reay","United States","IndyCar Series");

CREATE TABLE "vehicle_driver" (
"Driver_ID" int,
"Vehicle_ID" int,
PRIMARY KEY ("Driver_ID","Vehicle_ID"),
FOREIGN KEY ("Driver_ID") REFERENCES "driver"("Driver_ID"),
FOREIGN KEY ("Vehicle_ID") REFERENCES "vehicle"("Vehicle_ID")
);

INSERT INTO  "vehicle_driver" VALUES (1,1);
INSERT INTO  "vehicle_driver" VALUES (1,3);
INSERT INTO  "vehicle_driver" VALUES (1,5);
INSERT INTO  "vehicle_driver" VALUES (2,2);
INSERT INTO  "vehicle_driver" VALUES (2,6);
INSERT INTO  "vehicle_driver" VALUES (2,7);
INSERT INTO  "vehicle_driver" VALUES (2,8);
INSERT INTO  "vehicle_driver" VALUES (3,1);
INSERT INTO  "vehicle_driver" VALUES (4,1);
INSERT INTO  "vehicle_driver" VALUES (4,2);
INSERT INTO  "vehicle_driver" VALUES (4,6);

