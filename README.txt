
export API_KEY=xxx
curl -d "api_key=${API_KEY}" https://api.justseed.it/torrent/add.csp
curl -d "api_key=${API_KEY}" -d "url=magnet:?xt=urn:btih:e1464c60dc9a8a14f4b5805d5139bd41a08cc8c6&dn=Linux+kernel+0.01+%5B1991%5D&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80&tr=udp%3A%2F%2Ftracker.publicbt.com%3A80&tr=udp%3A%2F%2Ftracker.istole.it%3A6969&tr=udp%3A%2F%2Ftracker.ccc.de%3A80&tr=udp%3A%2F%2Fopen.demonii.com%3A1337" https://api.justseed.it/torrent/add.csp


udp://open.demonii.com:1337
udp://tracker.istole.it:6969
udp://tracker.justseed.it:1337
udp://tracker.openbittorrent.com:80
udp://tracker.publicbt.com:80