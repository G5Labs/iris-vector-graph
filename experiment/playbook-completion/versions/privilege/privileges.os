 set rs=##class(%SQL.Statement).%ExecDirect(,"SELECT * FROM Security.SQLPrivileges WHERE Grantee IN ('IVGAUDIT_RO','IVGAUDIT_RO_ROLE')")
 if rs.%SQLCODE<0 { write "<<PRIVQ:",rs.%SQLCODE," ",rs.%Message,":PRIVQ>>",! halt }
 set m=rs.%GetMetadata(), n=m.columns.Count(), k=0
 while rs.%Next() { set k=k+1, line="" for i=1:1:n { set line=line_m.columns.GetAt(i).colName_"="_rs.%GetData(i)_" " } write "PRIV ",line,! }
 write "<<PRIVCOUNT:",k,":PRIVCOUNT>>",!
 kill u do ##class(Security.Users).Get("IVGAUDIT_RO",.u) write "<<USERPROPS:roles=",$get(u("Roles"))," ns=",$get(u("NameSpace"))," enabled=",$get(u("Enabled")),":USERPROPS>>",!
 kill r do ##class(Security.Roles).Get("IVGAUDIT_RO_ROLE",.r) write "<<ROLEPROPS:resources=",$get(r("Resources"))," granted=",$get(r("GrantedRoles")),":ROLEPROPS>>",!
 halt
