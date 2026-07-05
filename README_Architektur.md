@startuml  
!include <C4/C4_Container>

title Tigers Coaching – Container Diagramm

Person(coach, "Coach", "Benutzt die Plattform zur Spielvorbereitung")  
Person(admin, "Admin", "Verwaltet Benutzer und Inhalte")

System_Boundary(tc, "Tigers Coaching") {  
Container(auth, "Auth", "Flask", "Login, Benutzerverwaltung und Service-Dashboard (JWT-Ausgabe)")  
Container(agenda, "Agenda", "Flask", "Liefert und verwaltet Trainingseinheiten")  
Container(analyse, "Analyse", "Flask", "Liefert LLM-Antworten")

ContainerDb(agendadb, "Agenda Datenbank", "PostgreSQL", "Speichert Trainingsdaten")  
ContainerDb(authdb, "Auth Datenbank", "PostgreSQL", "Speichert Benutzer und Rollen")  
}

System_Ext(llm, "AI Interface", "Externe Quelle für Analysen")

Rel(coach, auth, "Benutzt")  
Rel(admin, auth, "Benutzt")

Rel(auth, authdb, "verwendet")
Rel(auth, agenda, "JWT-geschützt")  
Rel(auth, analyse, "JWT-geschützt")

Rel(agenda, agendadb, "nutzt")  
Rel(analyse, llm, "nutzt")  

@enduml
