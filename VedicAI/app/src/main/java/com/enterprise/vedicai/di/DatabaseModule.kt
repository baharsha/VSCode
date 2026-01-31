package com.enterprise.vedicai.di

import android.content.Context
import androidx.room.Room
import com.enterprise.vedicai.data.local.PanchangDao
import com.enterprise.vedicai.data.local.VedicDatabase
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): VedicDatabase {
        return Room.databaseBuilder(
            context,
            VedicDatabase::class.java,
            "vedic_ai_db"
        )
        .fallbackToDestructiveMigration() // Allows schema changes during development without manual migrations
        .build()
    }

    @Provides
    fun providePanchangDao(database: VedicDatabase): PanchangDao {
        return database.panchangDao()
    }
}
