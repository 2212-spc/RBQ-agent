CREATE TABLE PilotSkills
  (pilot_name CHAR(15) NOT NULL,
  plane_name CHAR(15) NOT NULL,
  age INTEGER,
  PRIMARY KEY (pilot_name, plane_name),
  FOREIGN KEY (plane_name) REFERENCES Hangar(plane_name)
  );

  INSERT into PilotSkills VALUES ('Celko', 'Piper Cub', 23);
  INSERT into PilotSkills VALUES ('Higgins', 'B-52 Bomber', 34);
  INSERT into PilotSkills VALUES ('Higgins', 'F-14 Fighter', 50);
  INSERT into PilotSkills VALUES ('Higgins', 'Piper Cub', 30);
  INSERT into PilotSkills VALUES ('Jones'  , 'B-52 Bomber', 24);
  INSERT into PilotSkills VALUES ('Jones'  , 'F-14 Fighter', 32);
  INSERT into PilotSkills VALUES ('Smith'  , 'B-1 Bomber', 41);
  INSERT into PilotSkills VALUES ('Smith'  , 'B-52 Bomber', 26);
  INSERT into PilotSkills VALUES ('Smith'  , 'F-14 Fighter', 45);
  INSERT into PilotSkills VALUES ('Wilson' , 'B-1 Bomber', 52);
  INSERT into PilotSkills VALUES ('Wilson' , 'B-52 Bomber', 34);
  INSERT into PilotSkills VALUES ('Wilson' , 'F-14 Fighter', 24);
  INSERT into PilotSkills VALUES ('Wilson' , 'F-17 Fighter', 35);

  CREATE TABLE Hangar
  (plane_name CHAR(15) NOT NULL PRIMARY KEY,
   location CHAR(15)
  );

  INSERT INTO Hangar VALUES ('B-1 Bomber', 'Chicago');
  INSERT INTO Hangar VALUES ('B-52 Bomber', 'Austin');
  INSERT INTO Hangar VALUES ('F-14 Fighter', 'Boston');
  INSERT INTO Hangar VALUES ('Piper Cub', 'Seattle');
