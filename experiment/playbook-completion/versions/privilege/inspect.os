 write "<<VERSION:",$zv,":VERSION>>",!
 do ##class(Config.Namespaces).Get("AUDITB",.p) write "<<NS:globals=",p("Globals")," routines=",p("Routines"),":NS>>",!
 kill d do ##class(Config.Databases).Get(p("Globals"),.d) set db=##class(SYS.Database).%OpenId(d("Directory")) write "<<GRES:",db.ResourceName,":GRES>>",!
 kill d do ##class(Config.Databases).Get(p("Routines"),.d) set db=##class(SYS.Database).%OpenId(d("Directory")) write "<<RRES:",db.ResourceName,":RRES>>",!
 set rs=##class(%ResultSet).%New("Config.Databases:List") do rs.Execute("*") while rs.Next() { set n=rs.Get("Name") kill d do ##class(Config.Databases).Get(n,.d) set db=##class(SYS.Database).%OpenId(d("Directory")) write "DB ",n," ",d("Directory")," resource=",$select($isobject(db):db.ResourceName,1:"(not open)"),! }
 for r="%DB_%DEFAULT","%Native_ClassExecution","%Native_GlobalAccess","%Service_Bindings","%Service_CallIn" { kill q set sc=##class(Security.Resources).Get(r,.q) write "RESOURCE ",r," public=",$get(q("PublicPermission"),"?"),! }
 write "<<USER_EXISTS:",##class(Security.Users).Exists("IVGAUDIT_RO"),":USER_EXISTS>>",!
 write "<<ROLE_EXISTS:",##class(Security.Roles).Exists("IVGAUDIT_RO_ROLE"),":ROLE_EXISTS>>",!
 halt
