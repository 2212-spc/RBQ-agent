create table Sailors (
sid INTEGER primary key,
name TEXT,
rating INTEGER,
age INTEGER
);

CREATE TABLE Boats (
  bid INTEGER primary key,
  name TEXT,
  color TEXT
);

CREATE TABLE Reserves (
  sid INTEGER,
  bid INTEGER,
  day TEXT,
  foreign key (sid) references Sailors(sid),
  foreign key (bid) references Boats(bid)
);
