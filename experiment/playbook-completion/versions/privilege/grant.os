 for s="GRANT SELECT ON SCHEMA Graph_KG TO IVGAUDIT_RO_ROLE","GRANT EXECUTE ON SCHEMA Graph_KG TO IVGAUDIT_RO_ROLE" { set r=##class(%SQL.Statement).%ExecDirect(,s) write "<<SQL:",s," => ",r.%SQLCODE," ",r.%Message,":SQL>>",! }
 halt
