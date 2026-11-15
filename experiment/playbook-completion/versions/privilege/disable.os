 kill u set sc=##class(Security.Users).Get("IVGAUDIT_RO",.u) set u("Enabled")=0 set sc=##class(Security.Users).Modify("IVGAUDIT_RO",.u)
 write "<<DISABLE:",$system.Status.GetErrorText(sc),":DISABLE>>",!
 kill u do ##class(Security.Users).Get("IVGAUDIT_RO",.u) write "<<USERPROPS:roles=",$get(u("Roles"))," ns=",$get(u("NameSpace"))," enabled=",$get(u("Enabled")),":USERPROPS>>",!
 kill r do ##class(Security.Roles).Get("IVGAUDIT_RO_ROLE",.r) write "<<ROLEPROPS:resources=",$get(r("Resources"))," granted=",$get(r("GrantedRoles")),":ROLEPROPS>>",!
 halt
