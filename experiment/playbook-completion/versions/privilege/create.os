 set pw=$system.Util.GetEnviron("IVGAUDIT_PW") write "<<PWLEN:",$length(pw),":PWLEN>>",!
 if $length(pw)<16 { write "<<ABORT:no password in the environment:ABORT>>",! halt }
 if ##class(Security.Users).Exists("IVGAUDIT_RO")||##class(Security.Roles).Exists("IVGAUDIT_RO_ROLE") { write "<<ABORT:user or role already exists:ABORT>>",! halt }
 do ##class(Config.Namespaces).Get("AUDITB",.p) kill d do ##class(Config.Databases).Get(p("Globals"),.d) set gres=##class(SYS.Database).%OpenId(d("Directory")).ResourceName
 kill d do ##class(Config.Databases).Get(p("Routines"),.d) set rres=##class(SYS.Database).%OpenId(d("Directory")).ResourceName
 set res=gres_":R"_$select(rres'=gres:","_rres_":R",1:"")_",%Native_ClassExecution:U,%Native_GlobalAccess:U"
 write "<<RESOURCES:",res,":RESOURCES>>",!
 set sc=##class(Security.Roles).Create("IVGAUDIT_RO_ROLE","completion audit (versions lane): disposable least-privilege IVG reading role, ADMIN_GUIDE section 3 reading row, AUDITB",res)
 write "<<ROLE:",$system.Status.GetErrorText(sc),":ROLE>>",!
 set sc=##class(Security.Users).Create("IVGAUDIT_RO","IVGAUDIT_RO_ROLE",pw,"completion audit versions lane reader","AUDITB",,,0,1,"disposable; disabled at the end of the lane")
 write "<<USER:",$system.Status.GetErrorText(sc),":USER>>",!
 kill pw
 kill u do ##class(Security.Users).Get("IVGAUDIT_RO",.u) write "<<USERPROPS:roles=",$get(u("Roles"))," ns=",$get(u("NameSpace"))," enabled=",$get(u("Enabled"))," changepw=",$get(u("ChangePassword")),":USERPROPS>>",!
 kill r do ##class(Security.Roles).Get("IVGAUDIT_RO_ROLE",.r) write "<<ROLEPROPS:resources=",$get(r("Resources"))," granted=",$get(r("GrantedRoles")),":ROLEPROPS>>",!
 halt
