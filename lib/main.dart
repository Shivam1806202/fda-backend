import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import 'package:intl/intl.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  @override
  _HomePageState createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {

  TextEditingController drugController = TextEditingController();

  String startDate = "";
  String endDate = "";

  bool loading = false;
  String? downloadUrl;
  int? totalRecords;

  // 🔥 PICK DATE
  Future<void> pickDate(bool isStart) async {
    DateTime? picked = await showDatePicker(
      context: context,
      initialDate: DateTime.now(),
      firstDate: DateTime(2004),
      lastDate: DateTime.now(),
    );

    if (picked != null) {
      String formatted = DateFormat('yyyyMMdd').format(picked);

      setState(() {
        if (isStart) {
          startDate = formatted;
        } else {
          endDate = formatted;
        }
      });
    }
  }

  // 🔥 API CALL
  Future<void> fetchData() async {

    if (drugController.text.isEmpty || startDate.isEmpty || endDate.isEmpty) {
      showError("Please fill all fields");
      return;
    }

    setState(() {
      loading = true;
      downloadUrl = null;
      totalRecords = null;
    });

    String drug = drugController.text.trim();

    try {
      final response = await http.get(Uri.parse(
          "http://157.39.65.220:8000/download?drug=$drug&start=$startDate&end=$endDate"
      ));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        setState(() {
          downloadUrl = data["download_url"];
          totalRecords = data["total_records"];
        });

      } else {
        showError("Server error");
      }
    } catch (e) {
      showError("Connection error");
    }

    setState(() => loading = false);
  }

  // 🔥 ERROR
  void showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg))
    );
  }

  // 🔥 OPEN FILE
  Future<void> openFile() async {
    if (downloadUrl != null) {
      await launchUrl(Uri.parse(downloadUrl!));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("FDA ADR Extractor"),
        centerTitle: true,
      ),

      body: SingleChildScrollView(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [

            // 🔹 Drug Input
            TextField(
              controller: drugController,
              decoration: InputDecoration(
                labelText: "Drug Name (e.g. semaglutide)",
                border: OutlineInputBorder(),
              ),
            ),

            SizedBox(height: 15),

            // 🔹 Start Date
            ElevatedButton(
              onPressed: () => pickDate(true),
              child: Text(
                startDate.isEmpty
                    ? "Select Start Date"
                    : "Start: $startDate",
              ),
            ),

            SizedBox(height: 10),

            // 🔹 End Date
            ElevatedButton(
              onPressed: () => pickDate(false),
              child: Text(
                endDate.isEmpty
                    ? "Select End Date"
                    : "End: $endDate",
              ),
            ),

            SizedBox(height: 20),

            // 🔹 Fetch Button
            ElevatedButton(
              onPressed: loading ? null : fetchData,
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.symmetric(vertical: 15),
              ),
              child: loading
                  ? CircularProgressIndicator(color: Colors.white)
                  : Text("Fetch & Generate Excel"),
            ),

            SizedBox(height: 20),

            // 🔹 Result
            if (totalRecords != null)
              Card(
                elevation: 3,
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Text(
                        "Total Reports",
                        style: TextStyle(fontSize: 16),
                      ),
                      SizedBox(height: 5),
                      Text(
                        "$totalRecords",
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            SizedBox(height: 20),

            // 🔹 Download Button
            if (downloadUrl != null)
              ElevatedButton(
                onPressed: openFile,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green,
                  padding: EdgeInsets.symmetric(vertical: 15),
                ),
                child: Text("Download Excel"),
              ),

          ],
        ),
      ),
    );
  }
}