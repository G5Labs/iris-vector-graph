 kill u set sc=##class(Security.Users).Get("IVGAUDIT_RO",.u) set u("Enabled")=1 set sc=##class(Security.Users).Modify("IVGAUDIT_RO",.u)
 write "<<ENABLE:",$system.Status.GetErrorText(sc),":ENABLE>>",!
 kill u do ##class(Security.Users).Get("IVGAUDIT_RO",.u) write "<<USERPROPS:roles=",$get(u("Roles"))," ns=",$get(u("NameSpace"))," enabled=",$get(u("Enabled")),":USERPROPS>>",!
 halt
