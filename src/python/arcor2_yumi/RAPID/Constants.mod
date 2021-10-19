MODULE CONSTANTS
    PERS string ipController:="192.168.104.107";
    
    PERS tooldata currentTool:=[TRUE,[[0,0,0],[1,0,0,0]],[0.262,[7.8,11.9,50.7],[1,0,0,0],0.00022,0.00024,9E-5]];
    PERS wobjdata currentWobj:=[FALSE,TRUE,"",[[0,0,0],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
    
    PROC main()
        WHILE TRUE DO 
            WaitTime 10;
        ENDWHILE 
    ENDPROC 
      
ENDMODULE
