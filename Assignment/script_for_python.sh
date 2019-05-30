xterm -hold -title "Peer 1" -e "python3 cdht.py 1 3 4 300 0.3" &
xterm -hold -title "Peer 3" -e "python3 cdht.py  3 4 5 300 0.3" &
xterm -hold -title "Peer 4" -e "python3 cdht.py  4 5 8 300 0.3" &
xterm -hold -title "Peer 5" -e "python3 cdht.py  5 8 10 300 0.3" &
xterm -hold -title "Peer 8" -e "python3 cdht.py  8 10 12 300 0.3" &
xterm -hold -title "Peer 10" -e "python3 cdht.py  10 12 15 300 0.3" &
xterm -hold -title "Peer 12" -e "python3 cdht.py  12 15 1 300 0.3" &
xterm -hold -title "Peer 15" -e "python3 cdht.py  15 1 3 300 0.3" &
