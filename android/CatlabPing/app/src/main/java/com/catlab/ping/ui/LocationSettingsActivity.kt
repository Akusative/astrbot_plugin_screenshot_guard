/*
 * CatlabPing - 位置查岗设置页
 * Copyright (C) 2026 沈菀 (Akusative) - AGPL-3.0
 */

package com.catlab.ping.ui

import android.Manifest
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import com.catlab.ping.R
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import com.google.android.material.button.MaterialButton

class LocationSettingsActivity : AppCompatActivity() {

    private lateinit var prefs: SharedPreferences
    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var etHomeLat: EditText
    private lateinit var etHomeLng: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_location_settings)

        prefs = getSharedPreferences("catlab_ping", MODE_PRIVATE)
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)

        val etServerUrl = findViewById<EditText>(R.id.et_location_server)
        val etInterval = findViewById<EditText>(R.id.et_location_interval)
        etHomeLat = findViewById(R.id.et_home_lat)
        etHomeLng = findViewById(R.id.et_home_lng)
        val etAlertDistance = findViewById<EditText>(R.id.et_alert_distance)
        val btnGetLocation = findViewById<MaterialButton>(R.id.btn_get_current_location)
        val btnSave = findViewById<MaterialButton>(R.id.btn_location_save)

        // 恢复已保存的值
        etServerUrl.setText(prefs.getString("location_server", ""))
        etInterval.setText(prefs.getInt("location_interval", 10).toString())
        etHomeLat.setText(prefs.getString("home_lat", ""))
        etHomeLng.setText(prefs.getString("home_lng", ""))
        etAlertDistance.setText(prefs.getInt("alert_distance", 500).toString())

        // 📍 获取当前位置按钮
        btnGetLocation.setOnClickListener {
            getCurrentLocation()
        }

        btnSave.setOnClickListener {
            prefs.edit().apply {
                putString("location_server", etServerUrl.text.toString().trim())
                putInt("location_interval", etInterval.text.toString().toIntOrNull() ?: 10)
                putString("home_lat", etHomeLat.text.toString().trim())
                putString("home_lng", etHomeLng.text.toString().trim())
                putInt("alert_distance", etAlertDistance.text.toString().toIntOrNull() ?: 500)
                apply()
            }
            Toast.makeText(this, "✅ 设置已保存", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    private fun getCurrentLocation() {
        // 检查定位权限
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "请先在主页开启位置查岗以授予定位权限", Toast.LENGTH_LONG).show()
            return
        }

        Toast.makeText(this, "📍 正在获取当前位置...", Toast.LENGTH_SHORT).show()

        val cancellationToken = CancellationTokenSource()

        fusedLocationClient.getCurrentLocation(
            Priority.PRIORITY_HIGH_ACCURACY,
            cancellationToken.token
        ).addOnSuccessListener { location ->
            if (location != null) {
                etHomeLat.setText(String.format("%.6f", location.latitude))
                etHomeLng.setText(String.format("%.6f", location.longitude))
                Toast.makeText(this, "✅ 已获取当前位置", Toast.LENGTH_SHORT).show()
            } else {
                // 降级：尝试获取上次已知位置
                fusedLocationClient.lastLocation.addOnSuccessListener { lastLocation ->
                    if (lastLocation != null) {
                        etHomeLat.setText(String.format("%.6f", lastLocation.latitude))
                        etHomeLng.setText(String.format("%.6f", lastLocation.longitude))
                        Toast.makeText(this, "✅ 已获取上次已知位置", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(this, "❌ 无法获取位置，请确保GPS已开启", Toast.LENGTH_LONG).show()
                    }
                }
            }
        }.addOnFailureListener { e ->
            Toast.makeText(this, "❌ 获取位置失败: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }
}
