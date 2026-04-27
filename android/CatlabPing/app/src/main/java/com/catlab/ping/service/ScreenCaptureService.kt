/*
 * CatlabPing - 截屏前台服务
 * Copyright (C) 2026 沈菀 (Akusative) - AGPL-3.0
 *
 * 接收 MediaProjection 授权后，执行截屏并上传到服务器。
 * 此服务仅在需要截屏时启动，截屏完成后自动停止。
 */

package com.catlab.ping.service

import android.app.*
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.DisplayMetrics
import android.util.Log
import android.view.WindowManager
import androidx.core.app.NotificationCompat
import com.catlab.ping.MainActivity
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.IOException

class ScreenCaptureService : Service() {

    companion object {
        const val TAG = "ScreenCaptureService"
        const val CHANNEL_ID = "catlab_ping_screen_capture"
        const val NOTIFICATION_ID = 2002
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
    }

    private lateinit var prefs: SharedPreferences
    private var mediaProjection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private val client = OkHttpClient()
    private val handler = Handler(Looper.getMainLooper())

    override fun onCreate() {
        super.onCreate()
        prefs = getSharedPreferences("catlab_ping", MODE_PRIVATE)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        val resultCode = intent.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
        val resultData = intent.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)

        if (resultCode != Activity.RESULT_OK || resultData == null) {
            Log.e(TAG, "无效的 MediaProjection 授权数据")
            stopSelf()
            return START_NOT_STICKY
        }

        // 启动前台服务（必须在 mediaProjection 之前）
        val notification = buildNotification("📸 正在截屏...")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        // 获取 MediaProjection
        val projectionManager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        mediaProjection = projectionManager.getMediaProjection(resultCode, resultData)

        if (mediaProjection == null) {
            Log.e(TAG, "无法获取 MediaProjection")
            stopSelf()
            return START_NOT_STICKY
        }

        // 延迟一小段时间再截屏，确保用户已切回目标App
        handler.postDelayed({
            captureScreen()
        }, 500)

        return START_NOT_STICKY
    }

    private fun captureScreen() {
        try {
            // 获取屏幕参数
            val windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
            val metrics = DisplayMetrics()
            @Suppress("DEPRECATION")
            windowManager.defaultDisplay.getMetrics(metrics)

            val screenWidth = metrics.widthPixels
            val screenHeight = metrics.heightPixels
            val screenDensity = metrics.densityDpi

            // 创建 ImageReader
            imageReader = ImageReader.newInstance(screenWidth, screenHeight, PixelFormat.RGBA_8888, 2)

            // 创建 VirtualDisplay
            virtualDisplay = mediaProjection?.createVirtualDisplay(
                "CatlabPingCapture",
                screenWidth, screenHeight, screenDensity,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                imageReader!!.surface, null, handler
            )

            // 等待一帧画面
            handler.postDelayed({
                processImage(screenWidth, screenHeight)
            }, 300)

        } catch (e: Exception) {
            Log.e(TAG, "截屏失败: ${e.message}")
            cleanup()
        }
    }

    private fun processImage(width: Int, height: Int) {
        try {
            val image = imageReader?.acquireLatestImage()
            if (image == null) {
                Log.w(TAG, "未能获取到屏幕图像")
                cleanup()
                return
            }

            val planes = image.planes
            val buffer = planes[0].buffer
            val pixelStride = planes[0].pixelStride
            val rowStride = planes[0].rowStride
            val rowPadding = rowStride - pixelStride * width

            // 创建 Bitmap
            val bitmap = Bitmap.createBitmap(
                width + rowPadding / pixelStride,
                height,
                Bitmap.Config.ARGB_8888
            )
            bitmap.copyPixelsFromBuffer(buffer)
            image.close()

            // 裁剪到实际屏幕大小
            val croppedBitmap = Bitmap.createBitmap(bitmap, 0, 0, width, height)
            if (croppedBitmap != bitmap) {
                bitmap.recycle()
            }

            // 压缩为 JPEG
            val outputStream = ByteArrayOutputStream()
            croppedBitmap.compress(Bitmap.CompressFormat.JPEG, 80, outputStream)
            val imageBytes = outputStream.toByteArray()
            croppedBitmap.recycle()

            Log.i(TAG, "截屏成功，图片大小: ${imageBytes.size / 1024}KB")

            // 上传到服务器
            uploadScreenshot(imageBytes)

        } catch (e: Exception) {
            Log.e(TAG, "处理截屏图像失败: ${e.message}")
            cleanup()
        }
    }

    private fun uploadScreenshot(imageBytes: ByteArray) {
        val serverUrl = prefs.getString("screenshot_server", "") ?: ""
        val port = prefs.getInt("screenshot_port", 2313)
        val deviceName = prefs.getString("device_name", "Android") ?: "Android"

        if (serverUrl.isBlank()) {
            Log.w(TAG, "未配置服务器地址，跳过上传")
            cleanup()
            return
        }

        val url = "${serverUrl.trimEnd('/')}:${port}/screenshot/upload"

        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("device", deviceName)
            .addFormDataPart(
                "screenshot", "screenshot_${System.currentTimeMillis()}.jpg",
                imageBytes.toRequestBody("image/jpeg".toMediaType())
            )
            .build()

        val request = Request.Builder()
            .url(url)
            .post(body)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "截屏上传失败: ${e.message}")
                cleanup()
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (it.isSuccessful) {
                        Log.i(TAG, "截屏上传成功！")
                    } else {
                        Log.w(TAG, "截屏上传返回异常: ${it.code}")
                    }
                }
                cleanup()
            }
        })
    }

    private fun cleanup() {
        virtualDisplay?.release()
        virtualDisplay = null
        imageReader?.close()
        imageReader = null
        mediaProjection?.stop()
        mediaProjection = null
        stopSelf()
    }

    override fun onDestroy() {
        cleanup()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "截屏服务",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "CatlabPing 截屏服务"
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
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentIntent(pendingIntent)
            .setOngoing(false)
            .setSilent(true)
            .build()
    }
}
