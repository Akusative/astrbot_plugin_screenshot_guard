/*
 * CatlabPing - 位置查岗前台服务
 * Copyright (C) 2026 沈菀 (Akusative) - AGPL-3.0
 *
 * 定时获取GPS位置并POST到服务器的 /api/location/report 接口
 */

package com.catlab.ping.service

import android.Manifest
import android.app.*
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.Location
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.util.Log
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import com.catlab.ping.MainActivity
import com.google.android.gms.location.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException

class LocationService : Service() {

    companion object {
        const val TAG = "LocationService"
        const val CHANNEL_ID = "catlab_ping_location"
        const val NOTIFICATION_ID = 2002
    }

    private lateinit var prefs: SharedPreferences
    private lateinit var fusedLocationClient: FusedLocationProviderClient
    private lateinit var locationCallback: LocationCallback
    private val client = OkHttpClient()

    override fun onCreate() {
        super.onCreate()
        prefs = getSharedPreferences("catlab_ping", MODE_PRIVATE)
        createNotificationChannel()
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = buildNotification("📍 位置守护运行中")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        startLocationUpdates()

        Log.i(TAG, "位置服务已启动")
        return START_STICKY
    }

    override fun onDestroy() {
        try {
            fusedLocationClient.removeLocationUpdates(locationCallback)
        } catch (e: Exception) {
            Log.e(TAG, "移除位置更新失败: ${e.message}")
        }
        Log.i(TAG, "位置服务已停止")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startLocationUpdates() {
        val intervalMinutes = prefs.getInt("location_interval", 10)
        val intervalMs = intervalMinutes * 60 * 1000L

        val locationRequest = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, intervalMs)
            .setMinUpdateIntervalMillis(intervalMs / 2)
            .setWaitForAccurateLocation(false)
            .build()

        locationCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.lastLocation?.let { location ->
                    reportLocation(location)
                }
            }
        }

        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED) {
            Log.e(TAG, "缺少定位权限")
            stopSelf()
            return
        }

        fusedLocationClient.requestLocationUpdates(
            locationRequest, locationCallback, Looper.getMainLooper()
        )

        Log.i(TAG, "位置更新已启动，间隔 ${intervalMinutes} 分钟")
    }

    private fun reportLocation(location: Location) {
        val serverUrl = prefs.getString("location_server", "") ?: ""
        if (serverUrl.isBlank()) {
            Log.w(TAG, "未配置服务器地址，跳过上报")
            return
        }

        val homeLat = prefs.getString("home_lat", "")?.toDoubleOrNull()
        val homeLng = prefs.getString("home_lng", "")?.toDoubleOrNull()
        val alertDistance = prefs.getInt("alert_distance", 500)

        val url = "${serverUrl.trimEnd('/')}/api/location/report"

        val json = JSONObject().apply {
            put("lat", location.latitude)
            put("lng", location.longitude)
            put("accuracy", location.accuracy)
            put("timestamp", System.currentTimeMillis() / 1000)
            if (homeLat != null && homeLng != null) {
                val distance = FloatArray(1)
                Location.distanceBetween(
                    homeLat, homeLng,
                    location.latitude, location.longitude,
                    distance
                )
                put("distance_from_home", distance[0].toInt())
                put("is_home", distance[0] <= alertDistance)
            }
        }

        val body = json.toString().toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url(url)
            .post(body)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "位置上报失败: ${e.message}")
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (it.isSuccessful) {
                        Log.i(TAG, "位置上报成功: ${location.latitude}, ${location.longitude}")
                    } else {
                        Log.w(TAG, "位置上报返回异常: ${it.code}")
                    }
                }
            }
        })
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "位置守护",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "CatlabPing 位置守护服务"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("CatlabPing")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .build()
    }
}
