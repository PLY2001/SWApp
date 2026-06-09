#pragma once
#include <unordered_map>
#include <map>
//#include <string>
//#include <atlstr.h>
//#include <memory>
//#include <mutex>
#include <regex>//正则表达式
#include "glm/glm.hpp"
#include "glm/gtc/matrix_transform.hpp"
#include "glm/gtc/type_ptr.hpp"
// #include <thread>
// #include <mutex>
// #include <atomic>
// #include <omp.h>

#include <io.h> //获取目录文件名

//获取略缩图
#include <shobjidl_core.h>
#include <thumbcache.h>
#include <atlstr.h>

#include <Commdlg.h>//浏览文件

//SolidWorks
#include <atlbase.h> //com
#import "sldworks.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids  // SOLIDWORKS type library
#import "swconst.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids   // SOLIDWORKS constants type library
#import "swdimxpert.tlb" raw_interfaces_only, raw_native_types, no_namespace, named_guids  //SOLIDWORKS dimxpert library

namespace MyApp {

	struct MyAnnotation { //若有俩面之间的尺寸公差标注，那么这俩面都具有一样的MyAnnotation，但是定义在不同的MyFaceFeature中
		std::string Name;//标注名称
		CComBSTR NameBSTR;
		swDimXpertAnnotationType_e Type = swDimXpertAnnotationType_unknown;//标注类型
		double AccuracySize = 0;//公差或粗糙度精度(毫米)
		int AccuracyLevel = 0;//公差或粗糙度等级
		
		//标注基准
		int IsDatum = 0;//是否是标注基准
		std::string DatumName;//基准名称

		//表面粗糙度
		int IsSFSymbol = 0;//是否是表面粗糙度
		swSFSymType_e SFSType = swSFBasic;//表面粗糙度类型

		//形位公差
		int IsGeoTolerance = 0;//是否是形位公差
		std::vector<std::string> ToleranceDatumNames;//公差基准
		int hasMCM = 0;//形位公差是否有实体状态
		swDimXpertMaterialConditionModifier_e MCMType = swDimXpertMaterialConditionModifier_unknown;//实体状态类型，即形位公差标注中的M和L

		//尺寸公差
		int IsDimTolerance = 0;//是否是尺寸公差
		double DimSize = 0;//尺寸大小
	};//标注 

	struct MyFaceFeature {
		std::string Name;//特征名称
		//CComBSTR AppliedFaceNameBSTR;//所属面名称
		double FaceArea = 0;//面的面积(mm)
		swSurfaceTypes_e surfaceType = SREV_TYPE;
		int AnnotationCount = 0;//标注数量
		std::vector<MyAnnotation> AnnotationArray;//标注数组
	};//特征面

	enum class MyState {
		Nothing, Succeed, Failed
	};//程序当前操作状态
	enum class SWState {
		Connected, FileOpen, PropertyGot, MBDGot, ModelLoaded, MassPropertyGot
	};//SW交互状态

	class MyApplication {
	private:
		std::map<std::string, std::string> property;//记录自定义属性
		std::map<std::string, std::string> summary;//记录摘要

		std::string MyStateMessage[3] = { "Unfinished","Succeed!","Failed!" };//提示文本		
		std::map<SWState, MyState> SWStateMap = {
			 {SWState::Connected,   MyState::Nothing}
			,{SWState::FileOpen,    MyState::Nothing}
			,{SWState::PropertyGot, MyState::Nothing}
			,{SWState::MBDGot,      MyState::Nothing}
			,{SWState::ModelLoaded, MyState::Nothing}
			,{SWState::MassPropertyGot, MyState::Nothing}
		};//记录SW交互状态
		MyState myState = MyState::Nothing;//记录程序当前操作状态

		bool toLoadProjectAddress = false;//是否弹出项目地址窗口
		bool toLoadPathSetting = false;//是否弹出工作目录设置窗口
		
		long DimXpertAnnotationCount = 0;//MBD标注数
		long DimXpertFeatureCount = 0;//MBD特征数

		std::unordered_map<std::string, MyFaceFeature> FaceMap;//记录MBD信息[面 : 特征(标注1，标注2...)]
		
		std::unordered_map<swDimXpertAnnotationType_e, int> GeoTolMap = {
			 {swDimXpertGeoTol_Angularity              ,8}//倾斜度M
			,{swDimXpertGeoTol_Circularity			   ,1}//圆度
			,{swDimXpertGeoTol_CircularRunout		   ,2}//圆跳动度
			,{swDimXpertGeoTol_CompositeLineProfile	   ,0}//复合 线轮廓度？
			,{swDimXpertGeoTol_CompositePosition	   ,0}//复合 位置度M？
			,{swDimXpertGeoTol_CompositeSurfaceProfile ,0}//复合 面轮廓度？
			,{swDimXpertGeoTol_Concentricity		   ,9}//同心度、同轴度M
			,{swDimXpertGeoTol_Cylindricity			   ,3}//圆柱度
			,{swDimXpertGeoTol_Flatness				   ,4}//平面度
			,{swDimXpertGeoTol_LineProfile			   ,5}//线轮廓度
			,{swDimXpertGeoTol_Parallelism			   ,10}//平行度M
			,{swDimXpertGeoTol_Perpendicularity		   ,11}//垂直度M
			,{swDimXpertGeoTol_Position				   ,12}//位置度M
			,{swDimXpertGeoTol_Straightness			   ,13}//直线度M
			,{swDimXpertGeoTol_SurfaceProfile		   ,6}//面轮廓度
			,{swDimXpertGeoTol_Symmetry				   ,14}//对称度M
			,{swDimXpertGeoTol_Tangency				   ,0}//切线度？
			,{swDimXpertGeoTol_TotalRunout			   ,7}//全跳动
		};//MBD标注类型集合：形位公差
		std::unordered_map<swDimXpertAnnotationType_e, int> DimTolMap = {
			 {swDimXpertDimTol_AngleBetween            ,1}//面间夹角公差
			,{swDimXpertDimTol_ChamferDimension		   ,2}//倒角公差
			,{swDimXpertDimTol_CompositeDistanceBetween,0}//面间混合距离公差？
			,{swDimXpertDimTol_ConeAngle			   ,3}//圆锥角公差
			,{swDimXpertDimTol_CounterBore			   ,4}//反向钻孔公差
			,{swDimXpertDimTol_CounterSinkAngle		   ,5}//反向沉头角度公差
			,{swDimXpertDimTol_CounterSinkDiameter	   ,6}//反向沉头直径公差
			,{swDimXpertDimTol_Depth				   ,7}//深度公差
			,{swDimXpertDimTol_Diameter				   ,8}//直径公差
			,{swDimXpertDimTol_DistanceBetween		   ,9}//面间距离公差
			,{swDimXpertDimTol_Length				   ,10}//长度公差
			,{swDimXpertDimTol_PatternAngleBetween	   ,11}//图案间角度公差
			,{swDimXpertDimTol_Radius				   ,12}//半径公差
			,{swDimXpertDimTol_Width				   ,13}//宽度公差
		};//MBD标注类型集合：尺寸公差
		std::unordered_map<swSFSymType_e, int> SFSMap = {
			 {swSFBasic         ,1}//基本
			,{swSFMachining_Req	,2}//要求切削加工
			,{swSFDont_Machine  ,3}//禁止切削加工
		};//MBD标注类型集合：表面粗糙度
		std::unordered_map<swDimXpertMaterialConditionModifier_e, int> MCMMap = {
			 {swDimXpertMCM_LMC  ,1}
			,{swDimXpertMCM_MMC	 ,2}
			,{swDimXpertMCM_RFS  ,3}
		};//MBD标注类型集合：实体状态类型
		//std::unordered_map<std::string, int> FitTolMap;
		std::unordered_map<std::string, int> FitTolMap = {
	{"a9",5 },{"a10",6},{"a11",7},{"a12",7},{"a13",7},
	{"b8",4 },{"b9",5 },{"b10",6},{"b11",7},{"b12",7},{"b13",7},
	{"c8",4 },{"c9",5 },{"c10",6},{"c11",7},{"c12",7},{"cd5",1},{"cd6",2},{"cd7",3},{"cd8",4},{"cd9",5 },{"cd10",6},
	{"d5",1 },{"d6",2 },{"d7",3 },{"d8",4 },{"d9",5 },{"d10",6},{"d11",7},{"d12",7},{"d13",7},
	{"e5",1 },{"e6",2 },{"e7",3 },{"e8",4 },{"e9",5 },{"e10",6},{"ef3",1},{"ef4",1},{"ef5",1},{"ef6",2 },{"ef7",3 },{"ef8",4 },{"ef9",5 },{"ef10",6},
	{"f3",1 },{"f4",1 },{"f5",1 },{"f6",2 },{"f7",3 },{"f8",4 },{"f9",5 },{"f10",6},{"fg3",1},{"fg4",1 },{"fg5",1 },{"fg6",2 },{"fg7",3 },{"fg8",4 },{"fg9",5 },{"fg10",6},
	{"g3",1 },{"g4",1 },{"g5",1 },{"g6",2 },{"g7",3 },{"g8",4 },{"g9",5 },{"g10",6},
	{"h1",1 },{"h2",1 },{"h3",1 },{"h4",1 },{"h5",1 },{"h6",2 },{"h7",3 },{"h8",4 },{"h9",5 },{"h10",6 },{"h11",7 },{"h12",7 },{"h13",7 },{"h14",7 },{"h15",7 },{"h16",7 },{"h17",7 },{"h18",7 },
	{"js1",1},{"js2",1},{"js3",1},{"js4",1},{"js5",1},{"js6",2},{"js7",3},{"js8",4},{"js9",5},{"js10",6},{"js11",7},{"js12",7},{"js13",7},{"js14",7},{"js15",7},{"js16",7},{"js17",7},{"js18",7},{"j5",1 },{"j6",2 },{"j7",3  },{"j8",4  },
	{"k3",1 },{"k4",1 },{"k5",1 },{"k6",2 },{"k7",3 },{"k8",4 },{"k9",5 },{"k10",6},{"k11",7},{"k12",7 },{"k13",7 },
	{"m3",1 },{"m4",1 },{"m5",1 },{"m6",2 },{"m7",3 },{"m8",4 },{"m9",5 },
	{"n3",1 },{"n4",1 },{"n5",1 },{"n6",2 },{"n7",3 },{"n8",4 },{"n9",5 },
	{"p3",1 },{"p4",1 },{"p5",1 },{"p6",2 },{"p7",3 },{"p8",4 },{"p9",5 },{"p10",6},
	{"r3",1 },{"r4",1 },{"r5",1 },{"r6",2 },{"r7",3 },{"r8",4 },{"r9",5 },{"r10",6},
	{"s3",1 },{"s4",1 },{"s5",1 },{"s6",2 },{"s7",3 },{"s8",4 },{"s9",5 },{"s10",6},
	{"t5",1 },{"t6",2 },{"t7",3 },{"t8",4 },
	{"u5",1 },{"u6",2 },{"u7",3 },{"u8",4 },{"u9",5 },
	{"v5",1 },{"v6",2 },{"v7",3 },{"v8",4 },
	{"x5",1 },{"x6",2 },{"x7",3 },{"x8",4 },{"x9",5 },{"x10",6},
	{"y6",2 },{"y7",3 },{"y8",4 },{"y9",5 },{"y10",6},
	{"z6",2 },{"z7",3 },{"z8",4 },{"z9",5 },{"z10",6},{"z11",7},{"z6",2 },{"za7",3},{"za8",4},{"za9",5 },{"za10",6},{"za11",7},{"zb7",3 },{"zb8",4 },{"zb9",5 },{"zb10",6},{"zb11",7},{"zc7",3 },{"zc8",4},{"zc9",5},{"zc10",6},{"zc11",7},
	{"A9",5 },{"A10",6},{"A11",7},{"A12",7},{"A13",7},
	{"B8",4 },{"B9",5 },{"B10",6},{"B11",7},{"B12",7},{"B13",7},
	{"C8",4 },{"C9",5 },{"C10",6},{"C11",7},{"C12",7},{"CD5",1},{"CD6",2},{"CD7",3},{"CD8",4},{"CD9",5 },{"CD10",6},
	{"D5",1 },{"D6",2 },{"D7",3 },{"D8",4 },{"D9",5 },{"D10",6},{"D11",7},{"D12",7},{"D13",7},
	{"E5",1 },{"E6",2 },{"E7",3 },{"E8",4 },{"E9",5 },{"E10",6},{"EF3",1},{"EF4",1},{"EF5",1},{"EF6",2 },{"EF7",3 },{"EF8",4 },{"EF9",5 },{"EF10",6},
	{"F3",1 },{"F4",1 },{"F5",1 },{"F6",2 },{"F7",3 },{"F8",4 },{"F9",5 },{"F10",6},{"FG3",1},{"FG4",1 },{"FG5",1 },{"FG6",2 },{"FG7",3 },{"FG8",4 },{"FG9",5 },{"FG10",6},
	{"G3",1 },{"G4",1 },{"G5",1 },{"G6",2 },{"G7",3 },{"G8",4 },{"G9",5 },{"G10",6},
	{"H1",1 },{"H2",1 },{"H3",1 },{"H4",1 },{"H5",1 },{"H6",2 },{"H7",3 },{"H8",4 },{"H9",5 },{"H10",6 },{"H11",7 },{"H12",7 },{"H13",7 },{"H14",7 },{"H15",7 },{"H16",7 },{"H17",7 },{"H18",7 },
	{"JS1",1},{"JS2",1},{"JS3",1},{"JS4",1},{"JS5",1},{"JS6",2},{"JS7",3},{"JS8",4},{"JS9",5},{"JS10",6},{"JS11",7},{"JS12",7},{"JS13",7},{"JS14",7},{"JS15",7},{"JS16",7},{"JS17",7},{"JS18",7},{"J5",1 },{"J6",2 },{"J7",3  },{"J8",4  },
	{"K3",1 },{"K4",1 },{"K5",1 },{"K6",2 },{"K7",3 },{"K8",4 },{"K9",5 },{"K10",6},{"K11",7},{"K12",7 },{"K13",7 },
	{"M3",1 },{"M4",1 },{"M5",1 },{"M6",2 },{"M7",3 },{"M8",4 },{"M9",5 },
	{"N3",1 },{"N4",1 },{"N5",1 },{"N6",2 },{"N7",3 },{"N8",4 },{"N9",5 },
	{"P3",1 },{"P4",1 },{"P5",1 },{"P6",2 },{"P7",3 },{"P8",4 },{"P9",5 },{"P10",6},
	{"R3",1 },{"R4",1 },{"R5",1 },{"R6",2 },{"R7",3 },{"R8",4 },{"R9",5 },{"R10",6},
	{"S3",1 },{"S4",1 },{"S5",1 },{"S6",2 },{"S7",3 },{"S8",4 },{"S9",5 },{"S10",6},
	{"T5",1 },{"T6",2 },{"T7",3 },{"T8",4 },
	{"U5",1 },{"U6",2 },{"U7",3 },{"U8",4 },{"U9",5 },
	{"V5",1 },{"V6",2 },{"V7",3 },{"V8",4 },
	{"X5",1 },{"X6",2 },{"X7",3 },{"X8",4 },{"X9",5 },{"X10",6},
	{"Y6",2 },{"Y7",3 },{"Y8",4 },{"Y9",5 },{"Y10",6},
	{"Z6",2 },{"Z7",3 },{"Z8",4 },{"Z9",5 },{"Z10",6},{"Z11",7},{"Z6",2 },{"ZA7",3},{"ZA8",4},{"ZA9",5 },{"ZA10",6},{"ZA11",7},{"ZB7",3 },{"ZB8",4 },{"ZB9",5 },{"ZB10",6},{"ZB11",7},{"ZC7",3 },{"ZC8",4},{"ZC9",5},{"ZC10",6},{"ZC11",7},

		};//MBD标注类型集合：尺寸公差

		//char InputName[64] = "pipe";//用户输入名
		std::string CADName = "pole";//默认CAD文件名
		std::string CADType = ".SLDPRT";//默认CAD文件类型
		std::string CADPath = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\SWApp\\SolidWorks Part\\";//默认CAD文件路径
		std::string CADTempPath = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\SWApp\\SolidWorks Temp\\";//默认CAD临时文件路径

		int trianglesCount = 0;

		glm::vec3 MassCenter = glm::vec3(0);//重心坐标
		glm::vec3 MinBoxVertex = glm::vec3(0);//包围盒
		glm::vec3 MaxBoxVertex = glm::vec3(0);//包围盒

		std::vector<std::string> TotalCADNames;//当前目录下所以CAD文件名
		bool toAutomatization = false;//是否自动化

		int fileIndex = 0;//当前CAD文件索引

		//bool toShowMBD = true;//是否渲染视图考虑MBD语义

		bool toShowThumbnail = false;//是否显示略缩图

		std::string PictureExportPathForMBD = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\Pycharm Projects\\MBDViewFeature\\MBDViewDataset\\photos\\";
		std::string PictureExportPathFornoMBD = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\Pycharm Projects\\MBDViewFeature\\MBDViewDataset_noMBD\\photos\\";
		std::string ModelPictureExportPath = "C:\\Users\\PLY\\Desktop\\Files\\Projects\\Pycharm Projects\\MBDViewFeature\\MBDViewModelPicture\\";
		
		std::string PythonHome = "C:/Users/PLY/anaconda3/envs/torchgpu";
		std::string PythonProjectPath = "C:/Users/PLY/Desktop/Files/Projects/Pycharm Projects/MBDViewFeature";

		void EnableDocking();//开启Docking特性
		void ShowMenuBar();//显示菜单栏
		void ShowImguiExample();//显示Imgui示例
		bool ShowMessage(const char* message);//显示ImGui弹窗，而ImGui::OpenPopup("提示")用于弹出弹窗
		bool ShowPathSetting();//显示ImGui弹窗，而ImGui::OpenPopup("工作路径设置")用于弹出弹窗
		bool ConnectSW();//连接SW
		bool OpenFile();//打开文件
		bool ReadProperty();//读取文件属性
		bool ReadMassProperty();//获取质量属性
		bool ReadMBD();//读取MBD特征及其标注
		bool ReadNoMBDFace();
		bool LoadModel();//加载模型

		std::string GbkToUtf8(const char* src_str);//将SW默认文本的GBK编码转为ImGui显示文本用的Utf8编码
		bool ReadSafeArray(VARIANT* vt, VARENUM vtType, int dimensional, LPVOID* pData, LONG* itemCount);//读取SAFEARRAY数组(输入VARIANT变量，数组元素类型，数组维度，输出数组，输出数组大小)
		template<typename T>
		bool CreatVARIANTArray(int size, VARENUM type, T* buffer, VARIANT* array);//创建含SAFEARRAY的VARIANT变量(数组大小，数组元素类型，输入数组，输出VARIANT变量)
		double ReadDoubleFromString(std::string textstr);//读取字符串中的小数，如6.3
		wchar_t* multi_Byte_To_Wide_Char(const std::string& pKey);
		std::string string_To_UTF8(const std::string& str);
		void SetLinearDimAccuarcyLevel(int* level, double size, float f, float m, float c, float v);
		void SetSFSAccuarcyLevel(int* level, double size);
		void SetGeoAccuarcyLevel(int* level, double size, double faceArea, swDimXpertAnnotationType_e annoType);
		void SetGeoRealAccuarcyLevel(int* level, double size, float a, float b, float c, float d, float e, float f);
		
		void ReadAnnotationData(swDimXpertAnnotationType_e annoType,double* toleranceSize, int* toleranceLevel,std::string* myDatumName, std::vector<std::string>& datumNames,swDimXpertMaterialConditionModifier_e* MCMType, double* dimSize, double faceArea);//读取标注数据
		void DatumData(std::string* myDatumName);//读取基准信息
		void GeoTolData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel, std::vector<std::string>& datumNames, swDimXpertMaterialConditionModifier_e* MCMType, double faceArea);//读取形位公差数据
		void DimTolData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel, double* dimSize);//读取尺寸公差数据

		std::string GetFilesFromExplorer();
		bool CopyFileToCADPath();

		void GetFiles(std::string path, std::vector<std::string>& files);//读取当前目录下所有CAD文件名

	public:
		void ShowMyApp();
		inline std::unordered_map<std::string, MyFaceFeature>& GetFaceMap() { return FaceMap; };//获取面哈希表的引用
		inline std::map<SWState, MyState>& GetSWStateMap() { return SWStateMap; };//获取SW交互状态的引用
		inline std::string GetExportPathUtf8() { return CADTempPath + GetCADNameUtf8() + "\\"; };//获取保存模型时的路径
		inline std::string GetExportPath() { return CADTempPath + CADName + "\\"; };//获取保存模型时的路径
		inline std::string GetPictureExportPath(bool isMBDView) { return isMBDView? PictureExportPathForMBD : PictureExportPathFornoMBD; };//获取保存模型时的路径
		inline std::string GetModelPictureExportPath() { return ModelPictureExportPath; };//获取保存模型时的路径
		inline std::string GetCADName() { return CADName; };//获取保存模型时的名称
		inline std::string GetCADNameUtf8() { return string_To_UTF8(CADName); };//获取保存模型时的名称
		inline std::string GetCADPath() { return CADPath; };//获取保存模型时的路径
		inline std::string GetCADTempPath() { return CADTempPath; };//获取保存模型时的路径
		inline std::string GetPythonHome() { return PythonHome; };//获取python库的路径
		inline std::string GetPythonProjectPath() { return PythonProjectPath; };//获取python项目的路径
		inline glm::vec3 GetMassCenter() { return MassCenter; };//获取质心(毫米)
		inline glm::vec3 GetMinBoxVertex() { return MinBoxVertex; };//获取包围盒
		inline glm::vec3 GetMaxBoxVertex() { return MaxBoxVertex; };//获取包围盒
		inline int GetTrianglesCount() { return trianglesCount; };

		inline bool ShouldAutomatization() { return toAutomatization; }//确定要自动化
		inline void StopAutomatization() { toAutomatization = false; }//停止自动化
		//inline bool ShouldShowMBD() { return toShowMBD; }//确定要考虑MBD语义
		inline bool ShouldLoadThumbnail() { return toShowThumbnail; }//确定要加载略缩图
		inline void StopLoadThumbnail() { toShowThumbnail = false; }//停止加载略缩图
		inline void SetCADPath(std::string path) { CADPath = path; };//获取保存模型时的路径
		inline void SetCADTempPath(std::string path) { CADTempPath = path; };//获取保存模型时的路径
		inline void SetPictureExportPathForMBD(std::string path) {PictureExportPathForMBD = path;}
		inline void SetPictureExportPathFornoMBD(std::string path) { PictureExportPathFornoMBD = path; }
		inline void SetModelPictureExportPath(std::string path) { ModelPictureExportPath = path; }
		inline void SetPythonHome(std::string path) { PythonHome = path; }
		inline void SetPythonProjectPath(std::string path) { PythonProjectPath = path; }

		
		std::string GetNextToOpenFileName();//获取打开模型时的路径
		HBITMAP GetThumbnailEx();
		BOOL SaveBitmapToFile(HBITMAP hBitmap, const CString& szfilename);
		bool ClearFiles(std::string clearPath);

		bool StartOpenFile(std::string inputName);//打开文件
		bool StartReadProperty();//读取文件属性
		bool StartReadMassProperty();//获取质量属性
		bool StartReadMBD();//读取MBD特征及其标注
		bool StartLoadModel();//加载模型

		void StartOpenFileFromButton(std::string inputName);//由按钮打开文件

		long allTime = 0;//MBD读取总耗时
		long feTime = 0;//特征读取循环耗时（包含标注、面耗时）
		long aTime = 0;//标注读取循环耗时
		long fTime = 0;//面读取循环耗时
		long swaTime = 0;//表面粗糙度读取循环耗时
		long bTime = 0;//非MBD面读取循环耗时

		//模型初始姿态
		float angleList[3] = { 0,0,0 };

		///////////用于算法比较/////////////
		inline void SetCADName(std::string name) { CADName = name; };//获取保存模型时的名称
		inline void SetTrianglesCount(int count) { trianglesCount = count; };//获取保存模型时的名称
		inline void SetFaceMap(std::unordered_map<std::string, MyFaceFeature>& facemap) { FaceMap = facemap; };//获取面哈希表的引用
		inline void SetSWStateMap(std::map<SWState, MyState>& statemap) { SWStateMap = statemap; };//获取SW交互状态的引用

		//std::mutex mtx;
		//void FeatureLoop(int feIndex, IDispatch** & myfeData);
		//void AnnotationLoop(int aIndex, IDispatch**& myaData, MyFaceFeature &faceFeature);

	//极致简洁的单例模式，运用了static的性质
	private:
		static std::shared_ptr<MyApplication> instance;
		
		MyApplication() {};
		~MyApplication() {};
	public:
		static MyApplication& GetInstance() {
			static MyApplication instance;
			return instance;
		}
		

	};

	//class MyApplicationAdapter
	//{
	//private:
	//	MyApplication* t;
	//public:
	//	MyApplicationAdapter(MyApplication* t_) :t(t_) {}
	//	void operator()(int feIndex, IDispatch**& myfeData, MyFaceFeature& faceFeature) { t->AnnotationLoop(feIndex, myfeData, faceFeature); };
	//};


    
}
