for host in 10.188.2.251 172.16.229.136
do
 	scp -q load_test_realistic.py zq@$host:~/project/supervise
	if [ $? == 0 ]; then
		echo "sucess scp to $host"
	else
		echo "fail scp to $host"
	fi
done
